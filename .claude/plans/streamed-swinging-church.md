# 응답 속도 최적화 플랜

## Context

현재 chat_handler.py의 pre-LLM 파이프라인이 모든 작업을 **순차 실행**하여 800-7300ms의 불필요한 지연이 발생한다. 독립적인 작업들을 `asyncio.gather()`로 병렬화하면 300-2000ms 절약 가능.

현재 순차 흐름:
```
classify_emotion (100-300ms) → add_message (10-30ms) → context_build (500-1500ms)
→ web_search (1-5s, optional) → get_tools (200-500ms) → ReAct loop
```

## 변경 사항

### 1. context_service.py — longterm + graphrag 병렬 fetch

**파일**: `backend/core/services/context_service.py`

현재 `_add_longterm_context`와 `_add_graphrag_context`가 순차 실행(lines 205-208)되며, 둘 다 **sync 작업이 event loop를 블로킹**하는 문제도 있음.

변경:
- `_add_longterm_context` → `_fetch_longterm_data` (데이터만 fetch, `asyncio.to_thread` 사용)
- `_add_graphrag_context` → `_fetch_graphrag_data` (데이터만 fetch, `asyncio.to_thread` 사용)
- `build()` 내에서 두 fetch를 `asyncio.gather()`로 병렬 실행
- fetch 완료 후 optimizer에 순차적으로 `add_section()` (optimizer는 thread-safe하지 않음)

```python
# 현재 (순차, event loop 블로킹)
await self._add_longterm_context(optimizer, user_input, config)  # 200-600ms
await self._add_graphrag_context(optimizer, user_input, config)  # 10-50ms

# 변경 후 (병렬, event loop 논블로킹)
longterm_data, graphrag_data = await asyncio.gather(
    self._fetch_longterm_data(user_input, config),
    self._fetch_graphrag_data(user_input, config),
)
if longterm_data:
    # optimizer.add_section (순차)
if graphrag_data:
    # optimizer.add_section (순차)
```

**효과**: ~10-50ms 병렬화 이득 + event loop 블로킹 해소 (다른 요청 처리 개선)

### 2. chat_handler.py — pre-ReAct 파이프라인 병렬화

**파일**: `backend/core/chat_handler.py`

현재 lines 192-229에서 emotion → add_message → context → search → tools가 순차 실행됨.

의존성 분석 결과:
- `emotional_context`는 memory persistence용이지 LLM prompt에 사용되지 않음
- context_service.build()은 working memory를 읽으므로 user message가 먼저 추가되어야 함
- search, tools fetch는 완전 독립

변경:
```python
# Phase 1: user message 즉시 추가 (neutral emotion, ~10ms)
memory_manager.add_message("user", user_input, emotional_context="neutral")

# Phase 2: 4개 작업 병렬 실행
user_emotion, context_result, search_result, (mcp_client, available_tools) = (
    await asyncio.gather(
        classify_emotion(user_input),          # 100-300ms
        self.context_service.build(...),       # 500-1500ms
        self.search_service.search_if_needed(...),  # 1-5s
        self._fetch_tools(),                   # 200-500ms
        return_exceptions=True,
    )
)

# Phase 3: emotion 결과로 message 업데이트 (optional)
if emotion != "neutral" and memory_manager:
    working._messages[-1].emotional_context = emotion
```

에러 처리:
- `return_exceptions=True` 사용, 각 결과를 개별 검증
- context 실패 시 빈 `ContextResult` fallback
- search 실패 시 빈 `SearchResult` fallback
- tools 실패 시 빈 리스트 fallback

**효과**: 순차 800-7300ms → 병렬 max(300, 1500, 5000, 500) = **300-2000ms 절약**

### 3. tool_service.py — 도구 병렬 실행

**파일**: `backend/core/services/tool_service.py`

현재 `execute_tools()` (lines 79-119)에서 tool call을 `for` 루프로 순차 실행.

변경:
- deferred tools 분리 (기존 로직 유지)
- immediate tools를 `asyncio.gather()`로 병렬 실행
- 각 tool에 개별 try/except (한 tool 실패가 다른 tool에 영향 없도록)

```python
# 현재 (순차)
for fc in function_calls:
    result = await self.mcp_client.call_tool(name, args)

# 변경 후 (병렬)
immediate_results = await asyncio.gather(
    *[self._execute_single(name, args) for name, args in immediate_calls]
)
```

**효과**: 2+ 도구 호출 시 **500-2000ms 절약**

## 구현 순서

1. **context_service.py** (가장 안전, 자체 완결적 변경)
2. **tool_service.py** (자체 완결적 변경)
3. **chat_handler.py** (가장 큰 영향, 통합 테스트 필요)

## 수정 대상 파일

| 파일 | 변경 유형 |
|------|-----------|
| `backend/core/services/context_service.py` | `_add_longterm_context`/`_add_graphrag_context` → fetch/add 분리 + 병렬화 |
| `backend/core/services/tool_service.py` | `execute_tools()` 순차 루프 → `asyncio.gather()` |
| `backend/core/chat_handler.py` | lines 192-229 재구성: 병렬 파이프라인 |

## 재사용할 기존 패턴

- `asyncio.gather(..., return_exceptions=True)` — 이미 `memory_persistence_service.py:88`에서 사용 중
- `asyncio.to_thread()` — 이미 `memory_persistence_service.py:111`에서 사용 중
- `asyncio.create_task()` — 이미 `chat_handler.py:326`에서 사용 중

## 검증 방법

1. **기능 테스트**: `pytest tests/` — 기존 테스트 통과 확인
2. **수동 검증**: 서비스 재시작 후 대화 테스트, `CHAT done` 로그의 `dur_ms` 비교
3. **로그 확인**: `CTX build dur_ms`, `TOOL exec` 로그로 개별 작업 시간 확인
4. **에러 시나리오**: 각 병렬 작업의 개별 실패 시 전체 파이프라인이 정상 동작하는지 확인
