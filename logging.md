# Logging System

Axnmihn 프로젝트의 구조화된 로깅 시스템 문서입니다.

---

## 개요

이 로깅 시스템은 깔끔하고 읽기 쉬운 로그 출력을 제공합니다:
- 모듈별 컬러 출력
- 심각도 기반 색상
- 자동 축약어 변환
- `@logged` 데코레이터로 함수 진입/종료 자동 로깅
- 구조화된 key=value 포맷
- 요청 추적 및 경과 시간 표시
- 파일 로테이션 (10MB, 5개 백업)

---

## 모듈 컬러 레퍼런스

| 모듈 | 축약어 | 색상 | ANSI 코드 |
|------|--------|------|-----------|
| api | API | Bright Blue | `\033[94m` |
| core | COR | Cyan | `\033[96m` |
| memory | MEM | Light Magenta | `\033[95m` |
| llm | LLM | Light Green | `\033[92m` |
| mcp | MCP | Yellow | `\033[93m` |
| protocols | MCP | Yellow | `\033[93m` |
| media | MED | Orange | `\033[38;5;208m` |
| wake | WAK | Light Red | `\033[91m` |
| tools | TOL | White | `\033[97m` |

---

## 심각도 레벨

| 레벨 | 설명 | 사용 시점 |
|------|------|----------|
| **DEBUG** | 상세 진단 정보 | 함수 진입/종료, 내부 상태 확인 |
| **INFO** | 정상 작동 | 요청/응답, 중요 이벤트 |
| **WARNING** | 복구 가능한 문제 | 재시도, 폴백 처리 |
| **ERROR** | 주의 필요한 실패 | 예외 발생, 실패한 작업 |
| **CRITICAL** | 시스템 장애 | 서비스 중단, 치명적 오류 |

### 심각도별 색상

| 레벨 | 색상 | ANSI 코드 |
|------|------|-----------|
| DEBUG | Cyan | `\033[36m` |
| INFO | Green | `\033[32m` |
| WARNING | Yellow | `\033[33m` |
| ERROR | Red | `\033[31m` |
| CRITICAL | Magenta | `\033[35m` |

---

## 축약어 사전

로그 메시지를 간결하게 유지하기 위해 다음 축약어가 자동으로 적용됩니다:

### 일반 용어

| 원문 | 축약어 |
|------|--------|
| request | req |
| response | res |
| message | msg |
| error | err |
| config | cfg |
| connection | conn |
| timeout | tout |
| memory | mem |
| context | ctx |
| tokens | tok |
| function | fn |
| parameter | param |
| execution | exec |
| initialization | init |
| milliseconds | ms |
| seconds | sec |
| count | cnt |
| length | len |
| session | sess |
| entity | ent |
| device | dev |
| assistant | asst |

### 동작 관련

| 원문 | 축약어 |
|------|--------|
| received | recv |
| sent | sent |
| success | ok |
| failure | fail |
| building | build |
| processing | proc |
| completed | done |
| started | start |
| finished | fin |

### 기술 용어

| 원문 | 축약어 |
|------|--------|
| database | db |
| query | qry |
| result | res |
| input | in |
| output | out |
| latency | lat |
| duration | dur |
| provider | prov |
| model | mdl |

---

## 사용 예시

### 기본 로거 사용

```python
from backend.core.logging.logging import get_logger

logger = get_logger("api.chat")

# 기본 로깅
logger.info("Server started", port=8000, env="prod")
logger.debug("Processing request", user_id="abc123")
logger.warning("Rate limit approaching", remaining=10)
logger.error("Connection failed", host="db.local", retry=3)
```

### API 엔드포인트 로깅

```python
from backend.core.logging.logging import get_logger

logger = get_logger("api")

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    logger.info("Chat request received",
                session=request.session_id,
                model=request.model)

    try:
        result = await process_chat(request)
        logger.info("Chat completed",
                    tokens=result.total_tokens,
                    latency=result.latency_ms)
        return result
    except Exception as e:
        logger.error("Chat failed", error=str(e))
        raise
```

### Core 함수 로깅

```python
from backend.core.logging.logging import get_logger

logger = get_logger("core.chat_handler")

async def handle_message(message: str, context: dict):
    logger.debug("Processing message",
                 length=len(message),
                 context_keys=list(context.keys()))

    # 처리 로직
    result = await generate_response(message, context)

    logger.info("Response generated",
                model=result.model,
                tokens=result.tokens)
    return result
```

### Tool 함수 로깅

```python
from backend.core.logging.logging import get_logger

logger = get_logger("tools.hass_ops")

async def control_device(entity_id: str, action: str):
    logger.info("Controlling device",
                entity=entity_id,
                action=action)

    try:
        response = await hass_client.call_service(entity_id, action)
        logger.debug("Device responded",
                     state=response.state)
        return response
    except Exception as e:
        logger.error("Device control failed",
                     entity=entity_id,
                     error=str(e))
        raise
```

### @logged 데코레이터 사용

```python
from backend.core.logging.logging import logged

# 기본 사용 (진입/종료 로그)
@logged()
async def my_function(x, y):
    return x + y

# 인자와 결과값 포함
@logged(log_args=True, log_result=True)
def compute(data):
    return process(data)

# 진입 로그만
@logged(exit=False)
async def fire_and_forget(task):
    await background_task(task)

# INFO 레벨로 로깅
@logged(level=logging.INFO, log_args=True)
async def important_operation(config: dict):
    return await execute(config)
```

#### @logged 데코레이터 출력 예시

```
14:32:01.234 DEBUG [COR|chat_hand…] → my_function
14:32:01.567 DEBUG [COR|chat_hand…] ← my_function

# log_args=True 사용 시
14:32:01.234 DEBUG [COR|chat_hand…] → compute │ data=[3 items]
14:32:01.567 DEBUG [COR|chat_hand…] ← compute │ result=42

# 예외 발생 시
14:32:01.234 DEBUG [COR|chat_hand…] → my_function
14:32:01.567 ERROR [COR|chat_hand…] ✗ my_function │ error=Connection refused
```

---

## 설정

### 환경 변수

| 변수명 | 설명 | 기본값 | 예시 |
|--------|------|--------|------|
| `LOG_LEVEL` | 로그 레벨 설정 | `INFO` | `DEBUG`, `WARNING`, `ERROR` |
| `LOG_JSON` | JSON 로그 활성화 | `false` | `1`, `true`, `yes` |
| `NO_COLOR` | 컬러 출력 비활성화 | 미설정 | 아무 값 |

### 사용 예시

```bash
# 디버그 레벨로 실행
LOG_LEVEL=DEBUG python -m backend.app

# JSON 로그 활성화
LOG_JSON=true python -m backend.app

# 컬러 비활성화 (파이프라인 사용 시)
NO_COLOR=1 python -m backend.app | tee output.log
```

### 동적 레벨 변경

```python
from backend.core.logging.logging import set_log_level

# 런타임에 로그 레벨 변경
set_log_level("DEBUG")  # 상세 로그 활성화
set_log_level("WARNING")  # 경고 이상만 표시
```

---

## 출력 포맷

### 콘솔 출력 포맷

```
HH:MM:SS.mmm LVL [MOD|submod     ] msg │ k=v k2=v2
```

#### 포맷 구성 요소

| 구성 요소 | 설명 | 예시 |
|-----------|------|------|
| `HH:MM:SS.mmm` | 타임스탬프 (밀리초 포함) | `14:32:01.234` |
| `LVL` | 심각도 레벨 (5자) | `DEBUG`, ` INFO`, ` WARN`, `ERROR`, `CRIT!` |
| `MOD` | 모듈 축약어 (3자) | `API`, `COR`, `MEM` |
| `submod` | 서브모듈 이름 (최대 9자) | `chat`, `handler` |
| `msg` | 로그 메시지 | `Server started` |
| `│` | 구분자 | - |
| `k=v` | 키-값 쌍 | `port=8000 env=prod` |

### 실제 출력 예시

```
14:32:01.234  INFO [API|chat       ] Chat req recv │ sess=abc12345 mdl=gemini-3
14:32:01.456 DEBUG [COR|chat_hand…] → handle_message │ len=128
14:32:02.123  INFO [LLM|clients    ] Response done │ tok=1234 lat=667ms
14:32:02.234  WARN [MEM|permanent  ] Cache miss │ key=user_pref
14:32:02.345 ERROR [API|chat       ] Request fail │ err=timeout
```

### 파일 로그 포맷

파일 로그는 색상 없이 더 상세한 타임스탬프를 사용합니다:

```
2024-01-15 14:32:01.234 INFO    [abc12345│api.chat      ] Chat req recv │ sess=abc12345 mdl=gemini-3
```

### JSON 로그 포맷

`LOG_JSON=true` 설정 시 `logs/axnmihn.jsonl` 파일에 JSONL 형식으로 저장됩니다:

```json
{"ts":"2024-01-15T14:32:01.234567-08:00","level":"INFO","logger":"api.chat","msg":"Chat req recv","req":"abc12345","sess":"abc12345","mdl":"gemini-2"}
```

---

## 값 포맷팅

로그 값은 가독성을 위해 자동으로 포맷됩니다:

| 타입 | 포맷 | 예시 |
|------|------|------|
| `None` | `null` | `value=null` |
| `bool` | `yes`/`no` | `enabled=yes` |
| `int`/`float` | 그대로 | `count=42`, `ratio=0.95` |
| `list` (0-3개) | 전체 표시 | `items=[a, b, c]` |
| `list` (4개+) | 개수 표시 | `items=[15 items]` |
| `dict` | 키 개수 | `config={5 keys}` |
| `str` (60자+) | 잘라서 표시 | `content=Lorem ipsum dolor sit amet...` |

---

## 특수 키 하이라이트

특정 키는 시각적 구분을 위해 다른 색상으로 표시됩니다:

| 키 | 색상 | 용도 |
|----|------|------|
| `model`, `tier`, `provider` | Light Magenta | LLM 관련 정보 |
| `tokens`, `memories`, `working`, `longterm` | Light Cyan | 메모리 관련 정보 |
| `session` | Light Green | 세션 식별자 |
| `latency` | Yellow | 성능 메트릭 |
| `error` | Red | 에러 정보 |

---

## 요청 추적

요청 ID를 설정하면 해당 요청의 모든 로그에 자동으로 포함됩니다:

```python
from backend.core.logging.logging import set_request_id, reset_request_id

# 요청 시작 시
token = set_request_id("req-abc123")

try:
    # 이 블록 내의 모든 로그에 request ID가 포함됨
    await process_request()
finally:
    # 요청 종료 시 리셋
    reset_request_id(token)
```

경과 시간은 `request_tracker`가 활성화된 경우 자동으로 표시됩니다:

```
14:32:01.234  INFO [API|chat       ] Processing │ +1.2s
14:32:02.456  INFO [API|chat       ] Completed │ +2.4s
```

---

## 파일 구조

```
backend/
└── core/
    └── logging/
        └── logging.py     # 메인 로깅 모듈

logs/
├── axnmihn.log           # 일반 텍스트 로그 (로테이션)
└── axnmihn.jsonl         # JSON 로그 (LOG_JSON=true 시)
```

---

## 모범 사례

### 1. 적절한 로그 레벨 선택

```python
# DEBUG: 개발/디버깅용 상세 정보
logger.debug("Cache lookup", key=cache_key, hit=cache_hit)

# INFO: 운영 상태 파악에 필요한 정보
logger.info("Request processed", duration=elapsed_ms)

# WARNING: 주의가 필요하지만 서비스는 정상
logger.warning("Retry attempt", attempt=3, max=5)

# ERROR: 실패했지만 서비스는 계속 가능
logger.error("API call failed", service="hass", error=str(e))

# CRITICAL: 서비스 중단 수준의 문제
logger.critical("Database connection lost")
```

### 2. 구조화된 데이터 활용

```python
# 좋은 예 - 구조화된 키-값
logger.info("User action",
            user_id=user.id,
            action="login",
            ip=request.client.host)

# 피해야 할 예 - 문자열 포맷팅
logger.info(f"User {user.id} logged in from {request.client.host}")
```

### 3. 민감 정보 제외

```python
# 좋은 예 - 토큰 마스킹
logger.debug("Auth request", token=api_key[:8] + "...")

# 피해야 할 예 - 전체 토큰 노출
logger.debug("Auth request", token=api_key)  # 위험!
```

### 4. 예외 로깅

```python
try:
    await risky_operation()
except Exception as e:
    # exception()은 스택 트레이스 포함
    logger.exception("Operation failed", operation="risky")
```

---

## 문제 해결

### 로그가 출력되지 않는 경우

1. `LOG_LEVEL` 확인: `LOG_LEVEL=DEBUG`로 설정
2. 핸들러 확인: 로거가 올바르게 초기화되었는지 확인

### 색상이 표시되지 않는 경우

1. `NO_COLOR` 환경 변수 확인
2. 터미널이 ANSI 색상을 지원하는지 확인
3. 출력이 파일로 리다이렉트되면 자동으로 색상 비활성화

### 파일 로그가 생성되지 않는 경우

1. `logs/` 디렉토리 존재 확인
2. 쓰기 권한 확인
3. 디스크 공간 확인

---

## 변경 이력

- **v2.0**: 모듈별 컬러, 축약어 시스템, @logged 데코레이터 추가
- **v1.0**: 초기 구조화 로깅 시스템
