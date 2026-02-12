# GC-001: PG Memory GC Script Bundle (Phase 1-8)

## Metadata
| Field | Value |
|-------|-------|
| ID | GC-001 |
| Severity | HIGH |
| Files | Create: `scripts/pg_memory_gc.py`, `tests/scripts/test_pg_memory_gc.py` |
| Wave | 1 |
| Depends On | (none) |
| Blocks | INTEGRATION-VERIFY |

## Context
PostgreSQL 기반 메모리 시스템 (PgMemoryRepository, PgSessionRepository, PgMetaMemoryRepository, PgGraphRepository) 추가 후 GC 스크립트가 없음. 기존 `scripts/memory_gc.py`는 ChromaDB/SQLite 전용이므로 PG 전용 GC가 필요.

8개 Phase를 단일 스크립트에 번들하여 구현. 모두 `scripts/pg_memory_gc.py` 파일을 수정하므로 분리 불가.

## Reference Files
- `scripts/memory_gc.py` — GC 구조, CLI, phase 패턴
- `scripts/cleanup_messages.py:61-93` — KeyRotator 클래스
- `scripts/cleanup_messages.py:149-198` — Gemini 호출 + ThreadPoolExecutor
- `backend/memory/pg/connection.py` — PgConnectionManager API
- `backend/config.py` — DATABASE_URL, DEFAULT_GEMINI_MODEL
- `tests/memory/pg/` — mock PgConnectionManager fixture 패턴

## Phases

### Phase 1: Emoji Strip
- `remove_emoji()` 유틸 함수 구현
- `messages` 테이블: `content` 컬럼에서 이모지 제거
- `memories` 테이블: `content` 컬럼에서 이모지 제거
- UPDATE 쿼리로 in-place 수정

### Phase 2: LLM Summarize
- `KeyRotator` 클래스: `scripts/cleanup_messages.py:61-93` 패턴 참조
- `length(content) > 2000` 인 메시지를 Gemini로 요약
- `ThreadPoolExecutor` 사용하여 병렬 처리
- `backend/config.py`에서 `DEFAULT_GEMINI_MODEL`, API 키 로드

### Phase 3: Hash Dedup
- `_content_hash()`: content의 SHA-256 해시 계산
- 동일 해시를 가진 중복 레코드 중 `importance` 가장 높은 것만 보존
- 나머지 삭제

### Phase 4: Decay Cleanup
- 조건: `decayed_importance < 0.1 OR (importance < 0.1 AND access_count <= 1)`
- 해당 메모리 삭제

### Phase 5: Archive Cleanup
- `archived_messages` 테이블에서 90일 이상 된 레코드 삭제

### Phase 6: Meta Cleanup
- `memory_access_patterns` 테이블에서 30일 이상 된 레코드 삭제

### Phase 7: Knowledge Graph Cleanup
- `entities`: `mention_count < 3 AND created_at < NOW() - 30 days` 삭제
- `relations`: `weight < 0.1` 삭제
- Orphan relations (source/target entity 없는 것) 삭제

### Phase 8: VACUUM ANALYZE
- Autocommit 연결로 `VACUUM ANALYZE` 실행
- `PgConnectionManager`의 autocommit 모드 사용

## CLI Interface
```bash
# 상태 확인만
python scripts/pg_memory_gc.py check

# 전체 실행
python scripts/pg_memory_gc.py full

# Dry-run (실제 삭제 없이 대상만 출력)
python scripts/pg_memory_gc.py full --dry-run
```

## TDD 순서
1. Phase 1 테스트 작성 → Phase 1 구현
2. Phase 2 테스트 작성 → Phase 2 구현
3. Phase 3 테스트 작성 → Phase 3 구현
4. Phase 4 테스트 작성 → Phase 4 구현
5. Phase 5-7 테스트 작성 → Phase 5-7 구현
6. Phase 8 테스트 작성 → Phase 8 구현
7. CLI + dry-run 테스트 → CLI 구현

## Acceptance Criteria
- [ ] 모든 8 Phase 구현 완료
- [ ] `check` 명령: 각 테이블 row count 출력
- [ ] `full` 명령: Phase 1-8 순차 실행
- [ ] `--dry-run`: DRY-RUN 태그와 함께 대상만 출력, 실제 변경 없음
- [ ] Phase별 mock 테스트 통과
- [ ] dry-run 검증 테스트 통과
- [ ] `ruff check scripts/pg_memory_gc.py` 통과
- [ ] `python -m pytest tests/scripts/test_pg_memory_gc.py -v` 통과
