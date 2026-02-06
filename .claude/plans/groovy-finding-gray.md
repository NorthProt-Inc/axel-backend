# Chat 모델을 Gemini → Anthropic Claude Sonnet 4.5로 교체

## Context

현재 axnmihn 백엔드의 **모든** LLM 호출이 Gemini (google-genai SDK)를 통해 이루어지고 있다.
Chat 응답 모델만 Anthropic Claude (`claude-sonnet-4-5-20250929`)로 교체하여 응답 품질 개선을 시도한다.
유틸리티 작업(요약, 감정 분류, 메모리 중요도, 임베딩)은 Gemini에 그대로 유지한다.

- `ANTHROPIC_API_KEY` 환경변수는 이미 설정됨
- `anthropic` Python SDK 0.76.0은 venv에 이미 설치됨
- 기존 `BaseLLMClient` 추상 클래스가 있어 새 provider 추가가 용이

## 변경 파일

### 1. `backend/config.py` — Anthropic 설정 추가
- `ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")` 추가
- `ANTHROPIC_CHAT_MODEL` 설정 (`claude-sonnet-4-5-20250929`)
- `ANTHROPIC_THINKING_BUDGET` 설정 (기본 10000 tokens)
- 기존 `CHAT_MODEL`, `MODEL_NAME`, `DEFAULT_GEMINI_MODEL`은 변경하지 않음 (유틸리티용으로 유지)

### 2. `backend/llm/clients.py` — AnthropicClient 구현 (핵심)
- `_gemini_schema_to_anthropic()` 헬퍼 함수 추가 (UPPERCASED → lowercase 타입 변환)
- `AnthropicClient(BaseLLMClient)` 클래스 추가:
  - `AsyncAnthropic()` 사용 (native async, `ANTHROPIC_API_KEY` 환경변수 자동 사용)
  - `generate_stream()`: `client.messages.stream()` 사용, `(text, is_thought, function_call)` 튜플 yield
    - `system` 파라미터 사용 (Gemini처럼 user 메시지에 system prompt 합치지 않음)
    - `thinking: {"type": "enabled", "budget_tokens": N}` — enable_thinking=True일 때
    - Thinking 활성화 시 `temperature` 파라미터 제외 (Anthropic 제약)
    - `force_tool_call` + thinking 동시 사용 불가 → thinking 우선, `tool_choice: "auto"` 사용
    - Tool use 스트리밍: `input_json_delta` 누적 → `content_block_stop`에서 JSON 파싱 후 `{"name": ..., "args": {...}}` 형태로 yield
    - 이미지: `{"type": "image", "source": {"type": "base64", ...}}` 형태로 변환
  - `generate()`: `client.messages.create()` 사용 (non-streaming)
  - 자체 `CircuitBreakerState` 인스턴스 (Gemini와 독립)
  - Anthropic 에러 타입별 분류 (RateLimitError→429, OverloadedError→529, timeout)
  - 기존 `AdaptiveTimeout` 재사용
- `LLM_PROVIDERS`에 `"anthropic"` 항목 추가
- `DEFAULT_PROVIDER`를 `"anthropic"`으로 변경
- `get_llm_client()`에 `elif provider.provider == "anthropic"` 분기 추가

### 3. `backend/llm/router.py` — DEFAULT_MODEL 변경
- `DEFAULT_MODEL`의 `id`, `name`, `provider`, `model`을 anthropic으로 변경
- import를 `MODEL_NAME` → `ANTHROPIC_CHAT_MODEL`로 교체

### 4. `backend/llm/__init__.py` — export 추가
- `AnthropicClient` export 추가

### 5. `backend/core/mcp_client.py` — Anthropic용 tool 포맷 메서드 추가
- `get_anthropic_tools()` 메서드 추가
- `get_tools_with_schemas()`가 이미 `input_schema` 형태를 반환하므로, 이를 그대로 활용
- 별도 cache (`_anthropic_tools_cache`, `_anthropic_cache_timestamp`) 추가
- Core tool 우선순위 로직 재활용

### 6. `backend/core/chat_handler.py` — Chat path 전환
- `ChatRequest.model_choice` 기본값: `"gemini"` → `"anthropic"`
- `_fetch_tools()`: `get_gemini_tools()` → `get_anthropic_tools()`

### 7. `backend/api/openai.py` — API endpoint 전환
- 하드코딩된 `model_choice = "gemini"` → `"anthropic"` (line 73)

## 변경하지 않는 것

| 파일/기능 | 이유 |
|-----------|------|
| `backend/api/memory.py` | `get_llm_client("gemini")` 하드코딩, 유틸리티용 |
| `backend/memory/recent/summarizer.py` | `get_llm_client("gemini")` 하드코딩, 요약용 |
| 모든 임베딩 코드 | Gemini embedding 모델 사용 |
| `backend/core/services/emotion_service.py` | Gemini wrapper 직접 사용 |
| `backend/core/tools/opus_executor.py` | Claude CLI 서브프로세스, API 아님 |
| `config.py`의 `MODEL_NAME`, `DEFAULT_GEMINI_MODEL` | 유틸리티 작업용으로 유지 |

## 주요 Anthropic API 차이점 및 대응

| 항목 | Gemini | Anthropic | 대응 |
|------|--------|-----------|------|
| System prompt | User 메시지에 합침 | `system` 파라미터 | 분리 전달 |
| Tool 포맷 | `parameters` + UPPERCASED | `input_schema` + lowercase | 변환 헬퍼 / 직접 사용 |
| Thinking | `thinking_level: "high"` | `thinking: {type: "enabled", budget_tokens: N}` | Budget 기반 설정 |
| Thinking + temperature | 호환 | **비호환** | Thinking 시 temperature 제외 |
| Thinking + force_tool | 호환 | **비호환** (tool_choice "any" 불가) | Thinking 우선, auto fallback |
| Streaming | 동기 SDK + asyncio.Queue | Native async stream | 직접 async iteration |
| Tool call 감지 | `part.function_call` | `content_block_start/delta/stop` | JSON 누적 후 파싱 |
| 에러 타입 | 문자열 기반 | Typed exception | 양쪽 모두 처리 |

## 검증 방법

1. **서비스 재시작**: `systemctl --user restart axnmihn`
2. **헬스체크**: `curl http://localhost:8000/health`
3. **채팅 테스트**: Open WebUI 또는 curl로 채팅 요청 전송
4. **Tool 호출 테스트**: Tool 사용이 필요한 질문 (예: 날씨, 메모리 검색)으로 tool call 동작 확인
5. **Thinking 확인**: Thinking 이벤트가 정상적으로 스트리밍되는지 확인
6. **유틸리티 무영향 확인**: 메모리 저장, 요약 등이 기존과 동일하게 Gemini로 동작하는지 확인
7. **로그 확인**: `journalctl --user -u axnmihn -f`로 에러 없는지 모니터링
