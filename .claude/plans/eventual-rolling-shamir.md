# C++ Native 미사용 모듈 (`vector_ops`, `graph_ops`) 프로덕션 통합 계획

## Context

`backend/native/` C++ 모듈에 4개 서브모듈이 있으나, `decay_ops`와 `string_ops`만 프로덕션에서 사용 중이다.
`vector_ops`(cosine similarity, embedding 중복 탐지)와 `graph_ops`(BFS, connected components)는
빌드만 되고 테스트 외에 호출하는 코드가 없다. 이 두 모듈을 실제 코드에 통합한다.

## 핵심 분석

코드를 직접 읽어본 결과:
- **ChromaDB가 이미 벡터 유사도 검색을 처리**하므로 `facade.py:query()`나 `find_similar_memories()`에서 native vector_ops는 불필요
- **KnowledgeGraph는 string key** 사용, C++ graph_ops는 `size_t` key → 어댑터 필요
- **가장 ROI 높은 지점**: `memory_gc.py:phase2_semantic_dedup` (현재 N개 메모리마다 개별 API 호출)

---

## Step 1: `vector_ops.find_duplicates_by_embedding` → `memory_gc.py:phase2_semantic_dedup`

**ROI: 최고** — 현재 가장 느린 GC phase를 근본적으로 개선

**현재 문제** (`scripts/memory_gc.py:82-158`):
```
for each memory (N개):
    embedding = API 호출 (느림)           # N번 API 호출
    similar = ChromaDB 쿼리 (느림)        # N번 DB 쿼리
    → 중복이면 삭제 대상에 추가
```
- 500개 메모리 기준 500번의 embedding API 호출 + 500번의 ChromaDB 쿼리

**개선 후**:
```
all_data = ChromaDB.get(include=["embeddings"])   # 1번 DB 호출 (임베딩 포함)
duplicates = native.vector_ops.find_duplicates_by_embedding(
    embeddings, threshold=DUPLICATE_THRESHOLD
)                                                  # C++ AVX2 O(N²) 일괄 처리
→ 중복 쌍 목록에서 삭제 대상 결정
```
- API 호출 0번, DB 쿼리 1번, C++ 배치 비교 1번

**수정 파일**: `scripts/memory_gc.py`
- `phase2_semantic_dedup()` 함수 (lines 82-158) 리팩토링
- native import 패턴은 `decay_calculator.py`의 try/except fallback 패턴 재사용

**기대 효과**: GC Phase 2 실행 시간 10-30배 단축 (API 호출 제거가 핵심)

---

## Step 2: `graph_ops` 어댑터 레이어 → `graph_rag.py`

**ROI: 중간** — 그래프 규모가 커질수록 효과 증가

**현재 문제** (`backend/memory/graph_rag.py:129-147, 156-181`):
- `get_neighbors()`: Python set 기반 BFS (lines 129-147)
- `find_path()`: Python list 기반 BFS (lines 156-181)
- `adjacency` dict의 key가 `str` → C++ `size_t` 변환 필요

**구현 방안**: `KnowledgeGraph`에 string↔int 매핑 레이어 추가
```python
# graph_rag.py 내부
_node_to_idx: Dict[str, int] = {}   # "mark" → 0
_idx_to_node: Dict[int, str] = {}   # 0 → "mark"
_native_adjacency: Dict[int, List[int]] = {}  # C++ 전달용
```

**수정 파일**: `backend/memory/graph_rag.py`
- `KnowledgeGraph._rebuild_native_index()`: entity 추가/삭제 시 인덱스 리빌드
- `KnowledgeGraph.get_neighbors()`: native 사용 가능 시 `graph_ops.bfs_neighbors()` 호출
- `KnowledgeGraph.find_path()`: native 사용 불가 (경로 추적이 필요, C++에는 없음) → Python 유지

**native 호출 기준**: entity 100개 이상일 때만 native 사용 (소규모 그래프는 Python이 충분)

---

## Step 3: `graph_ops.find_connected_components` → `dedup_knowledge_graph.py`

**ROI: 중간** — isolated cluster 탐지로 dead entity 정리 강화

**현재 문제** (`scripts/dedup_knowledge_graph.py:191-217`):
- `find_dead_entities()`는 mentions=0 + 관계 없음 + 7일 이상만 확인
- 관계는 있지만 메인 그래프에서 **고립된 소규모 클러스터**는 탐지 불가

**개선**: connected components 분석을 dead entity 탐지에 추가
```python
# 메인 컴포넌트 외의 작은 클러스터(3개 이하 노드)를 dead 후보로 추가
components = native.graph_ops.find_connected_components(adjacency, n_nodes)
main_component_id = most_common(components)
small_clusters = [node for node, comp in enumerate(components)
                  if comp != main_component_id and cluster_size[comp] <= 3]
```

**수정 파일**: `scripts/dedup_knowledge_graph.py`
- `find_dead_entities()` 함수에 connected components 기반 탐지 추가
- Step 2의 string↔int 매핑 패턴 재사용

---

## Step 4: `vector_ops.cosine_similarity_batch` → `dedup_knowledge_graph.py` (embedding 기반 중복 탐지)

**ROI: 낮음~중간** — 현재 string similarity만으로 충분하나, embedding 기반 추가 시 정확도 향상

**현재**: Phase 3 string similarity (Levenshtein)만 사용
**개선**: string similarity + embedding similarity 이중 검증

- knowledge graph entity에 임베딩이 있다면 `find_duplicates_by_embedding()`으로 의미적 중복도 탐지
- 현재 entity에 임베딩 필드가 없으므로 **후순위** (임베딩 추가 인프라 필요)

---

## 실행 순서

| 순서 | 대상 | 수정 파일 | 난이도 | 즉시 효과 |
|------|------|-----------|--------|-----------|
| **1** | `phase2_semantic_dedup` 네이티브화 | `scripts/memory_gc.py` | 낮음 | 최고 |
| **2** | graph string↔int 어댑터 | `backend/memory/graph_rag.py` | 중간 | 중간 |
| **3** | connected components 탐지 | `scripts/dedup_knowledge_graph.py` | 낮음 | 중간 |
| **4** | embedding 기반 entity 중복 | `scripts/dedup_knowledge_graph.py` | 높음 | 낮음 |

## 검증 방법

1. **Step 1**: `python scripts/memory_gc.py full --dry-run` 실행 후 Phase 2 결과가 기존과 동일한지 비교
2. **Step 2**: 기존 테스트 + `get_neighbors()` 결과가 Python/native 양쪽 동일한지 assert
3. **Step 3**: `python scripts/dedup_knowledge_graph.py --dry-run` 실행 후 새로 발견된 dead entity 목록 확인
4. 전체: `pytest tests/memory/` 통과 확인
