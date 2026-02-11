# Axnmihn

<details open>
<summary><strong>🇰🇷 한국어</strong></summary>

**AI 어시스턴트 백엔드 시스템**

FastAPI 기반의 AI 백엔드 서비스입니다. 6계층 메모리 시스템, MCP 생태계, 멀티 LLM 프로바이더를 통합한 현대적인 아키텍처를 제공합니다.

**기술 스택:** Python 3.12 / FastAPI / ChromaDB / SQLite / PostgreSQL (선택) / C++17 네이티브 모듈

**라이선스:** MIT

---

## ✨ 주요 기능

- **6계층 메모리 시스템** — M0(이벤트 버퍼) → M1(워킹 메모리) → M3(세션 아카이브) → M4(장기 메모리) → M5.1-5.3(MemGPT/GraphRAG/MetaMemory)
- **멀티 LLM 지원** — Gemini 3 Flash, Claude Sonnet 4.5, Circuit Breaker & Fallback
- **MCP 생태계** — 메모리, 파일, 시스템, 리서치, Home Assistant 통합
- **SIMD 최적화** — C++17 네이티브 모듈 (메모리 decay, 벡터 연산, 그래프 탐색)
- **음성 파이프라인** — Deepgram Nova-3 (STT) + Qwen3-TTS / OpenAI TTS
- **OpenAI 호환 API** — `/v1/chat/completions` 엔드포인트
- **적응형 페르소나** — 채널별 AI 성격 자동 조정
- **컨텍스트 최적화** — 토큰 예산 기반 스마트 컨텍스트 조립

---

## 🏗️ 아키텍처

```
                      +------------------------------------------+
                      |          AXNMIHN BACKEND (FastAPI)        |
                      |                                          |
  Client              |  +----------+  +----------+  +--------+ |
  (axel-chat / CLI    |  |   API    |  |  Memory  |  | Media  | |
   / Open WebUI)      |  | Routers  |  | Manager  |  | (TTS/  | |
        |              |  |          |  |          |  |  STT)  | |
        v              |  +----+-----+  +----+-----+  +---+----+ |
   +---------+         |       |             |            |      |
   | OpenAI  | REST/   |       v             v            v      |
   | Compat  | SSE     |  +----+-------------+------------+----+ |
   | API     | ------> |  |          LLM Router                | |
   +---------+         |  |  Gemini 3 Flash | Claude Sonnet 4.5 | |
                       |  +----+---------------------------+---+ |
                       |       |                           |     |
                       |       v                           v     |
                       |  +---------+    +-----------------------------+
                       |  |  MCP    |    |    6-Layer Memory System    |
                       |  | Server  |    |                             |
                       |  +---------+    | M0: Event Buffer            |
                       |                 | M1: Working Memory          |
                       |                 | M3: Session Archive (SQL)   |
                       |                 | M4: Long-Term (ChromaDB)    |
                       |                 | M5.1: MemGPT (budget)       |
                       |                 | M5.2: GraphRAG (knowledge)  |
                       |                 | M5.3: MetaMemory (access)   |
                       |                 +-----------------------------+
                       +------------------------------------------+
                                        |
                            +-----------+-----------+
                            |           |           |
                            v           v           v
                       Home Asst.   Playwright   Research
                       (WiZ/IoT)    (Browser)    (Tavily +
                                                 DuckDuckGo)
```

### 핵심 컴포넌트

| 컴포넌트 | 기술 | 목적 |
|----------|------|------|
| API 서버 | FastAPI + Uvicorn | Async HTTP/SSE, OpenAI 호환 |
| LLM 라우터 | Gemini 3 Flash + Claude Sonnet 4.5 | 멀티 프로바이더, Circuit Breaker |
| 메모리 시스템 | 6계층 아키텍처 | 세션 간 지속적인 컨텍스트 |
| MCP 서버 | Model Context Protocol (SSE) | 도구 생태계 |
| 네이티브 모듈 | C++17 + pybind11 | SIMD 최적화 (그래프/decay) |
| 오디오 | Deepgram Nova-3 (STT) + Qwen3-TTS / OpenAI (TTS) | 음성 파이프라인 |
| Home Assistant | REST API | IoT 디바이스 제어 |
| 리서치 | Playwright + Tavily + DuckDuckGo | 웹 리서치 |

---

## 💾 6계층 메모리 시스템

메모리 시스템은 6개의 기능 계층 (M0, M1, M3, M4, M5.1-5.3)으로 구성되며 `MemoryManager`(`backend/memory/unified.py`)가 오케스트레이션합니다.

```
  User Message
       |
       v
  M0 Event Buffer -----> 실시간 이벤트 스트림
       |
       v
  M1 Working Memory ----> 인메모리 deque (20턴)
       |                   JSON 영속화
       |
       | 즉시 영속화
       v
  M3 Session Archive ----> SQLite (또는 PostgreSQL)
       |                    세션, 메시지, 상호작용 로그
       |
       | 통합 시
       v
  M4 Long-Term Memory ---> ChromaDB (또는 PostgreSQL + pgvector)
       |                    3072차원 Gemini 임베딩
       |                    적응형 decay, 중복 제거
       |
       +--- M5.1 MemGPT ------> 예산 기반 메모리 선택
       |                         토큰 예산 컨텍스트 조립
       |
       +--- M5.2 GraphRAG -----> 엔티티-관계 지식 그래프
       |                         spaCy NER + LLM 추출
       |                         BFS 탐색 (100+ 엔티티 시 C++)
       |
       +--- M5.3 MetaMemory ---> 접근 패턴 추적
                                  핫 메모리 감지
```

### 계층 상세

| 계층 | 파일 | 저장소 | 목적 |
|------|------|--------|------|
| M0 Event Buffer | `memory/event_buffer.py` | 인메모리 | 실시간 이벤트 스트리밍 |
| M1 Working Memory | `memory/current.py` | `data/working_memory.json` | 현재 대화 버퍼 (20턴) |
| M3 Session Archive | `memory/recent/` | `data/sqlite/sqlite_memory.db` | 세션 요약, 메시지 히스토리 |
| M4 Long-Term Memory | `memory/permanent/` | `data/chroma_db/` | 시맨틱 벡터 검색, 중요도 decay |
| M5.1 MemGPT | `memory/memgpt.py` | 인메모리 | 토큰 예산 선택, 주제 다양성 |
| M5.2 GraphRAG | `memory/graph_rag.py` | `data/knowledge_graph.json` | 엔티티/관계 그래프, BFS 탐색 |
| M5.3 MetaMemory | `memory/meta_memory.py` | SQLite | 접근 빈도, 채널 다양성 |

### 메모리 Decay

메모리는 적응형 망각 곡선을 사용하여 시간이 지남에 따라 감소합니다:

```
decayed_importance = importance * decay_factor

decay_factor = f(
    time_elapsed,           # 지수적 시간 감소
    base_rate=0.001,        # MEMORY_BASE_DECAY_RATE로 설정
    access_count,           # 반복 접근 시 decay 둔화
    connection_count,       # 그래프 연결된 메모리는 decay 저항
    memory_type_modifier    # 사실은 대화보다 천천히 decay
)

삭제 임계값: 0.03   (MEMORY_DECAY_DELETE_THRESHOLD)
최소 보존: 0.3      (MEMORY_MIN_RETENTION)
유사도 중복 제거: 0.90  (MEMORY_SIMILARITY_THRESHOLD)
```

### 컨텍스트 조립

`MemoryManager.build_smart_context()`는 문자 예산 내에서 모든 계층의 컨텍스트를 조립합니다:

| 섹션 | 기본 예산 (문자) | 설정 키 |
|------|-----------------|---------|
| 시스템 프롬프트 | 20,000 | `BUDGET_SYSTEM_PROMPT` |
| 시간 컨텍스트 | 5,000 | `BUDGET_TEMPORAL` |
| 워킹 메모리 | 80,000 | `BUDGET_WORKING_MEMORY` |
| 장기 메모리 | 30,000 | `BUDGET_LONG_TERM` |
| GraphRAG | 12,000 | `BUDGET_GRAPHRAG` |
| 세션 아카이브 | 8,000 | `BUDGET_SESSION_ARCHIVE` |

### PostgreSQL 백엔드 (선택)

`DATABASE_URL` 설정 시 SQLite/ChromaDB 대신 PostgreSQL + pgvector 사용:

```
backend/memory/pg/
  connection.py            # PgConnectionManager (연결 풀)
  memory_repository.py     # PgMemoryRepository (ChromaDB 대체)
  graph_repository.py      # PgGraphRepository (JSON 그래프 대체)
  session_repository.py    # PgSessionRepository (SQLite 대체)
  meta_repository.py       # PgMetaMemoryRepository
  interaction_logger.py    # PgInteractionLogger
```

필요: `pgvector/pgvector:pg17` (`docker-compose.yml` 참조)

---

## 🔌 API 엔드포인트

모든 엔드포인트는 `AXNMIHN_API_KEY` 헤더 인증이 필요합니다.

### 헬스 & 상태

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/health` | GET | 전체 헬스체크 (메모리, LLM, 모듈) |
| `/health/quick` | GET | 최소 생존 확인 |
| `/auth/status` | GET | 인증 상태 |
| `/llm/providers` | GET | 사용 가능한 LLM 프로바이더 |
| `/models` | GET | 사용 가능한 모델 |

### 채팅 (OpenAI 호환)

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/v1/chat/completions` | POST | 채팅 완성 (스트리밍/비스트리밍) |

### 메모리

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/memory/consolidate` | POST | Decay + 페르소나 진화 트리거 |
| `/memory/stats` | GET | 메모리 계층 통계 |
| `/memory/search?query=&limit=` | GET | 시맨틱 메모리 검색 |
| `/memory/sessions` | GET | 최근 세션 요약 |
| `/memory/session/{session_id}` | GET | 세션 상세 |
| `/session/end` | POST | 현재 세션 종료 |

### 오디오

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/v1/audio/transcriptions` | POST | STT (Deepgram Nova-3) |
| `/v1/audio/speech` | POST | TTS 합성 |

---

## 🛠️ MCP 생태계

SSE 전송을 통해 제공되는 도구들. 카테고리:

- **Memory:** store_memory, retrieve_context, memory_stats, ...
- **File:** read_file, list_directory, get_source_code
- **System:** run_command, search_codebase, read_system_logs, system_status, ...
- **Research:** web_search, visit_webpage, deep_research, tavily_search, ...
- **Home Assistant:** hass_control_light, hass_control_device, hass_read_sensor, ...
- **Delegation:** delegate_to_opus, google_deep_research

도구 표시 여부는 `MCP_DISABLED_TOOLS` 및 `MCP_DISABLED_CATEGORIES` 환경 변수로 설정 가능합니다.

---

## ⚡ 네이티브 C++ 모듈

C++17 + pybind11 + SIMD (AVX2/NEON)를 통한 성능 크리티컬 연산:

```
backend/native/src/
  axnmihn_native.cpp      # pybind11 바인딩
  decay.cpp/.hpp           # 메모리 decay (SIMD 배치)
  vector_ops.cpp/.hpp      # 코사인 유사도, 중복 감지
  string_ops.cpp/.hpp      # Levenshtein 거리
  graph_ops.cpp/.hpp       # BFS 탐색
  text_ops.cpp/.hpp        # 텍스트 처리
```

모듈이 설치되지 않은 경우 모든 호출 지점은 순수 Python으로 폴백됩니다.

```bash
cd backend/native && pip install .
# 필요: CMake 3.18+, C++17 컴파일러, pybind11
```

---

## ⚙️ 설정

### 환경 변수 (`.env`)

```bash
# LLM 프로바이더
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=                     # TTS 폴백
TAVILY_API_KEY=                     # 검색
DEEPGRAM_API_KEY=                   # STT

# 모델
DEFAULT_GEMINI_MODEL=gemini-3-flash-preview
CHAT_MODEL=gemini-3-flash-preview
ANTHROPIC_CHAT_MODEL=claude-sonnet-4-5-20250929
ANTHROPIC_THINKING_BUDGET=10000
EMBEDDING_MODEL=models/gemini-embedding-001
EMBEDDING_DIMENSION=3072

# 서버
HOST=0.0.0.0
PORT=8000
AXNMIHN_API_KEY=                    # API 인증
TZ=America/Vancouver

# PostgreSQL (선택 - PG 모드 활성화)
DATABASE_URL=postgresql://user:pass@localhost:5432/db
PG_POOL_MIN=2
PG_POOL_MAX=10

# 메모리 예산 (문자)
BUDGET_SYSTEM_PROMPT=20000
BUDGET_TEMPORAL=5000
BUDGET_WORKING_MEMORY=80000
BUDGET_LONG_TERM=30000
BUDGET_GRAPHRAG=12000
BUDGET_SESSION_ARCHIVE=8000

# 메모리 Decay
MEMORY_BASE_DECAY_RATE=0.001
MEMORY_MIN_RETENTION=0.3
MEMORY_DECAY_DELETE_THRESHOLD=0.03
MEMORY_SIMILARITY_THRESHOLD=0.90
MEMORY_MIN_IMPORTANCE=0.25

# 컨텍스트
CONTEXT_WORKING_TURNS=20
CONTEXT_FULL_TURNS=6
CONTEXT_MAX_CHARS=500000

# TTS
TTS_SERVICE_URL=http://127.0.0.1:8002
TTS_SYNTHESIS_TIMEOUT=30.0

# Home Assistant
HASS_URL=http://homeassistant.local:8123
HASS_TOKEN=
```

---

## 🚀 빠른 시작

### 옵션 A: Docker (권장)

```bash
git clone https://github.com/NorthProt-Inc/axnmihn.git
cd axnmihn

cp .env.example .env
# .env 파일에서 API 키 설정

docker compose up -d

# 확인
curl http://localhost:8000/health/quick
```

이렇게 시작됩니다: backend (8000) + MCP (8555) + research (8766) + PostgreSQL (5432) + Redis (6379).

### 옵션 B: 로컬 개발

```bash
git clone https://github.com/NorthProt-Inc/axnmihn.git
cd axnmihn

python3.12 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

cp .env.example .env
# .env 파일에서 API 키 설정

# (선택) 네이티브 C++ 모듈
cd backend/native && pip install . && cd ../..

# (선택) 리서치용 Playwright
playwright install chromium

# (선택) PostgreSQL + Redis
docker compose up -d postgres redis

# 실행
uvicorn backend.app:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```

---

## 🐳 배포

### Docker Compose (전체 스택)

```bash
docker compose up -d              # 모든 서비스 시작
docker compose ps                 # 상태
docker compose logs backend -f    # 백엔드 로그 팔로우
docker compose down               # 모두 중지
```

| 서비스 | 포트 | 이미지/타겟 | 리소스 |
|--------|------|------------|--------|
| `backend` | 8000 | Dockerfile → runtime | 4G RAM, 2 CPU |
| `mcp` | 8555 | Dockerfile → runtime | 1G RAM, 1 CPU |
| `research` | 8766 | Dockerfile → research | 2G RAM, 1.5 CPU |
| `postgres` | 5432 | pgvector/pgvector:pg17 | - |
| `redis` | 6379 | redis:7-alpine (256MB) | - |

TTS (GPU 의존)는 docker-compose.yml에서 주석 처리되어 있습니다. NVIDIA GPU 사용 가능 시 주석 해제하세요.

### Systemd 서비스 (베어메탈)

| 서비스 | 포트 | 목적 | 리소스 |
|--------|------|------|--------|
| `axnmihn-backend` | 8000 | FastAPI 백엔드 | 4G RAM, 200% CPU |
| `axnmihn-mcp` | 8555 | MCP 서버 (SSE) | 1G RAM, 100% CPU |
| `axnmihn-research` | 8766 | Research MCP | 2G RAM, 150% CPU |
| `axnmihn-tts` | 8002 | TTS 마이크로서비스 (Qwen3-TTS) | 4G RAM, 200% CPU |
| `axnmihn-wakeword` | - | Wakeword 감지 | 512M RAM, 50% CPU |
| `context7-mcp` | 3002 | Context7 MCP | 1G RAM |
| `markitdown-mcp` | 3001 | Markitdown MCP | 1G RAM |

자세한 운영 가이드는 [OPERATIONS.md](OPERATIONS.md) 참조.

### 유지보수

| 스크립트 | 목적 |
|---------|------|
| `scripts/memory_gc.py` | 메모리 가비지 컬렉션 (중복 제거, decay, 초과 크기 제거) |
| `scripts/db_maintenance.py` | SQLite VACUUM, ANALYZE, 무결성 체크 |
| `scripts/dedup_knowledge_graph.py` | 지식 그래프 중복 제거 |
| `scripts/regenerate_persona.py` | 7일 증분 페르소나 업데이트 |
| `scripts/optimize_memory.py` | 4단계 메모리 최적화 (텍스트 정리, 역할 정규화) |
| `scripts/cleanup_messages.py` | LLM 기반 메시지 정리 (병렬, 체크포인트) |
| `scripts/populate_knowledge_graph.py` | 지식 그래프 초기 채우기 |
| `scripts/night_ops.py` | 자동화된 야간 리서치 |
| `scripts/run_migrations.py` | 데이터베이스 스키마 마이그레이션 |

---

## 📁 프로젝트 구조

```
axnmihn/
├── backend/
│   ├── app.py                    # FastAPI 진입점, 라이프스팬
│   ├── config.py                 # 모든 설정
│   ├── api/                      # HTTP 라우터 (status, chat, memory, mcp, media, audio, openai)
│   ├── core/                     # 핵심 서비스
│   │   ├── chat_handler.py       # 메시지 라우팅
│   │   ├── context_optimizer.py  # 컨텍스트 크기 관리
│   │   ├── mcp_client.py        # MCP 클라이언트
│   │   ├── mcp_server.py        # MCP 서버 설정
│   │   ├── health/              # 헬스 모니터링
│   │   ├── identity/            # AI 페르소나 (ai_brain.py)
│   │   ├── intent/              # 의도 분류
│   │   ├── logging/             # 구조화된 로깅
│   │   ├── mcp_tools/           # 도구 구현
│   │   ├── persona/             # 채널 적응
│   │   ├── resilience/          # Circuit breaker, 폴백
│   │   ├── security/            # 프롬프트 방어
│   │   ├── session/             # 세션 상태
│   │   ├── telemetry/           # 상호작용 로깅
│   │   └── utils/               # 캐시, 재시도, HTTP 풀, Gemini 클라이언트
│   ├── llm/                     # LLM 프로바이더 (Gemini, Anthropic)
│   ├── media/                   # TTS 관리자
│   ├── memory/                  # 6계층 메모리 시스템
│   │   ├── unified.py           # MemoryManager 오케스트레이터
│   │   ├── event_buffer.py      # M0: 이벤트 버퍼
│   │   ├── current.py           # M1: 워킹 메모리
│   │   ├── recent/              # M3: 세션 아카이브 (SQLite)
│   │   ├── permanent/           # M4: 장기 (ChromaDB)
│   │   ├── memgpt.py            # M5.1: 예산 선택
│   │   ├── graph_rag.py         # M5.2: 지식 그래프
│   │   ├── meta_memory.py       # M5.3: 접근 추적
│   │   ├── temporal.py          # 시간 컨텍스트
│   │   └── pg/                  # PostgreSQL 백엔드 (선택)
│   ├── native/                  # C++17 확장 모듈
│   ├── protocols/mcp/           # MCP 프로토콜 핸들러
│   └── wake/                    # Wakeword + 음성 대화
├── tests/                       # pytest 테스트 스위트
├── scripts/                     # 자동화 스크립트
├── data/                        # 런타임 데이터 (SQLite, ChromaDB, JSON)
├── logs/                        # 애플리케이션 로그
├── storage/                     # 리서치 아티팩트, 크론 보고서
├── Dockerfile                   # 멀티스테이지 (runtime + research)
├── docker-compose.yml           # 전체 스택 (app + PG + Redis)
├── .dockerignore
├── pyproject.toml               # 프로젝트 메타데이터
└── .env                         # 환경 설정
```

---

## 📚 문서

- [OPERATIONS.md](OPERATIONS.md) — 운영 가이드 (한/영)
- [AGENTS.md](AGENTS.md) — 커스텀 에이전트 정의
- [logging.md](logging.md) — 로깅 시스템 문서
- [backend/native/README.md](backend/native/README.md) — C++ 네이티브 모듈
- `.github/instructions/` — 개발 지침 (TDD, 보안, 성능, 에러 분석)

---

## 🤝 기여

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

**커밋 규칙:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, etc.)

**코드 스타일:**
- Python: `black` 포매팅, `ruff` 린트, type hints 필수
- 함수 최대 400줄, 파일 최대 800줄
- Protocol 기반 인터페이스, dataclass/pydantic 데이터
- async def 우선 (I/O-bound 작업)

---

## 📄 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 참조

---

## 🙏 감사의 말

- **FastAPI** — 현대적인 웹 프레임워크
- **ChromaDB** — 벡터 데이터베이스
- **Anthropic & Google** — LLM API
- **Deepgram** — 음성 인식
- **Model Context Protocol** — 도구 통합 표준

---

**제작:** NorthProt Inc.  
**문의:** [GitHub Issues](https://github.com/NorthProt-Inc/axnmihn/issues)

</details>

---

<details>
<summary><strong>🇺🇸 English</strong></summary>

**AI Assistant Backend System**

A modern FastAPI-based AI backend service featuring a 6-layer memory system, MCP ecosystem, and multi-LLM provider integration.

**Tech Stack:** Python 3.12 / FastAPI / ChromaDB / SQLite / PostgreSQL (optional) / C++17 Native Module

**License:** MIT

---

## ✨ Key Features

- **6-Layer Memory System** — M0(Event Buffer) → M1(Working Memory) → M3(Session Archive) → M4(Long-Term) → M5.1-5.3(MemGPT/GraphRAG/MetaMemory)
- **Multi-LLM Support** — Gemini 3 Flash, Claude Sonnet 4.5, Circuit Breaker & Fallback
- **MCP Ecosystem** — Memory, File, System, Research, Home Assistant integration
- **SIMD Optimization** — C++17 native module (memory decay, vector ops, graph traversal)
- **Voice Pipeline** — Deepgram Nova-3 (STT) + Qwen3-TTS / OpenAI TTS
- **OpenAI-Compatible API** — `/v1/chat/completions` endpoint
- **Adaptive Persona** — Channel-specific AI personality adjustment
- **Context Optimization** — Token-budget-based smart context assembly

---

## 🏗️ Architecture

```
                      +------------------------------------------+
                      |          AXNMIHN BACKEND (FastAPI)        |
                      |                                          |
  Client              |  +----------+  +----------+  +--------+ |
  (axel-chat / CLI    |  |   API    |  |  Memory  |  | Media  | |
   / Open WebUI)      |  | Routers  |  | Manager  |  | (TTS/  | |
        |              |  |          |  |          |  |  STT)  | |
        v              |  +----+-----+  +----+-----+  +---+----+ |
   +---------+         |       |             |            |      |
   | OpenAI  | REST/   |       v             v            v      |
   | Compat  | SSE     |  +----+-------------+------------+----+ |
   | API     | ------> |  |          LLM Router                | |
   +---------+         |  |  Gemini 3 Flash | Claude Sonnet 4.5 | |
                       |  +----+---------------------------+---+ |
                       |       |                           |     |
                       |       v                           v     |
                       |  +---------+    +-----------------------------+
                       |  |  MCP    |    |    6-Layer Memory System    |
                       |  | Server  |    |                             |
                       |  +---------+    | M0: Event Buffer            |
                       |                 | M1: Working Memory          |
                       |                 | M3: Session Archive (SQL)   |
                       |                 | M4: Long-Term (ChromaDB)    |
                       |                 | M5.1: MemGPT (budget)       |
                       |                 | M5.2: GraphRAG (knowledge)  |
                       |                 | M5.3: MetaMemory (access)   |
                       |                 +-----------------------------+
                       +------------------------------------------+
                                        |
                            +-----------+-----------+
                            |           |           |
                            v           v           v
                       Home Asst.   Playwright   Research
                       (WiZ/IoT)    (Browser)    (Tavily +
                                                 DuckDuckGo)
```

### Core Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API Server | FastAPI + Uvicorn | Async HTTP/SSE, OpenAI-compatible |
| LLM Router | Gemini 3 Flash + Claude Sonnet 4.5 | Multi-provider, circuit breaker |
| Memory System | 6-layer architecture | Persistent context across sessions |
| MCP Server | Model Context Protocol (SSE) | Tool ecosystem |
| Native Module | C++17 + pybind11 | SIMD-optimized graph/decay ops |
| Audio | Deepgram Nova-3 (STT) + Qwen3-TTS / OpenAI (TTS) | Voice pipeline |
| Home Assistant | REST API | IoT device control |
| Research | Playwright + Tavily + DuckDuckGo | Web research |

---

## 💾 6-Layer Memory System

The memory system consists of 6 functional layers (M0, M1, M3, M4, M5.1-5.3) orchestrated by `MemoryManager` (`backend/memory/unified.py`).

```
  User Message
       |
       v
  M0 Event Buffer -----> real-time event stream
       |
       v
  M1 Working Memory ----> in-memory deque (20 turns)
       |                   JSON persistence
       |
       | immediate persist
       v
  M3 Session Archive ----> SQLite (or PostgreSQL)
       |                    sessions, messages, interaction logs
       |
       | on consolidation
       v
  M4 Long-Term Memory ---> ChromaDB (or PostgreSQL + pgvector)
       |                    3072-dim Gemini embeddings
       |                    adaptive decay, deduplication
       |
       +--- M5.1 MemGPT ------> budget-aware memory selection
       |                         token-budgeted context assembly
       |
       +--- M5.2 GraphRAG -----> entity-relation knowledge graph
       |                         spaCy NER + LLM extraction
       |                         BFS traversal (C++ for 100+ entities)
       |
       +--- M5.3 MetaMemory ---> access pattern tracking
                                  hot memory detection
```

### Layer Details

| Layer | File | Storage | Purpose |
|-------|------|---------|---------|
| M0 Event Buffer | `memory/event_buffer.py` | In-memory | Real-time event streaming |
| M1 Working Memory | `memory/current.py` | `data/working_memory.json` | Current conversation buffer (20 turns) |
| M3 Session Archive | `memory/recent/` | `data/sqlite/sqlite_memory.db` | Session summaries, message history |
| M4 Long-Term Memory | `memory/permanent/` | `data/chroma_db/` | Semantic vector search, importance decay |
| M5.1 MemGPT | `memory/memgpt.py` | In-memory | Token-budget selection, topic diversity |
| M5.2 GraphRAG | `memory/graph_rag.py` | `data/knowledge_graph.json` | Entity/relation graph, BFS traversal |
| M5.3 MetaMemory | `memory/meta_memory.py` | SQLite | Access frequency, channel diversity |

### Memory Decay

Memories decay over time using an adaptive forgetting curve:

```
decayed_importance = importance * decay_factor

decay_factor = f(
    time_elapsed,           # exponential time decay
    base_rate=0.001,        # configurable via MEMORY_BASE_DECAY_RATE
    access_count,           # repeated access slows decay
    connection_count,       # graph-connected memories resist decay
    memory_type_modifier    # facts decay slower than conversations
)

deletion threshold: 0.03   (MEMORY_DECAY_DELETE_THRESHOLD)
min retention: 0.3         (MEMORY_MIN_RETENTION)
similarity dedup: 0.90     (MEMORY_SIMILARITY_THRESHOLD)
```

### Context Assembly

`MemoryManager.build_smart_context()` assembles context from all layers within character budgets:

| Section | Default Budget (chars) | Config Key |
|---------|----------------------|------------|
| System Prompt | 20,000 | `BUDGET_SYSTEM_PROMPT` |
| Temporal Context | 5,000 | `BUDGET_TEMPORAL` |
| Working Memory | 80,000 | `BUDGET_WORKING_MEMORY` |
| Long-Term Memory | 30,000 | `BUDGET_LONG_TERM` |
| GraphRAG | 12,000 | `BUDGET_GRAPHRAG` |
| Session Archive | 8,000 | `BUDGET_SESSION_ARCHIVE` |

### PostgreSQL Backend (Optional)

When `DATABASE_URL` is set, the system uses PostgreSQL + pgvector instead of SQLite/ChromaDB:

```
backend/memory/pg/
  connection.py            # PgConnectionManager (connection pool)
  memory_repository.py     # PgMemoryRepository (replaces ChromaDB)
  graph_repository.py      # PgGraphRepository (replaces JSON graph)
  session_repository.py    # PgSessionRepository (replaces SQLite)
  meta_repository.py       # PgMetaMemoryRepository
  interaction_logger.py    # PgInteractionLogger
```

Requires: `pgvector/pgvector:pg17` (see `docker-compose.yml`)

---

## 🔌 API Endpoints

All endpoints require `AXNMIHN_API_KEY` header authentication.

### Health & Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Full health check (memory, LLM, modules) |
| `/health/quick` | GET | Minimal liveness check |
| `/auth/status` | GET | Auth status |
| `/llm/providers` | GET | Available LLM providers |
| `/models` | GET | Available models |

### Chat (OpenAI-Compatible)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat completion (streaming/non-streaming) |

### Memory

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/memory/consolidate` | POST | Trigger decay + persona evolution |
| `/memory/stats` | GET | Memory layer statistics |
| `/memory/search?query=&limit=` | GET | Semantic memory search |
| `/memory/sessions` | GET | Recent session summaries |
| `/memory/session/{session_id}` | GET | Session detail |
| `/session/end` | POST | End current session |

### Audio

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/audio/transcriptions` | POST | STT (Deepgram Nova-3) |
| `/v1/audio/speech` | POST | TTS synthesis |

---

## 🛠️ MCP Ecosystem

Tools served via SSE transport. Categories:

- **Memory:** store_memory, retrieve_context, memory_stats, ...
- **File:** read_file, list_directory, get_source_code
- **System:** run_command, search_codebase, read_system_logs, system_status, ...
- **Research:** web_search, visit_webpage, deep_research, tavily_search, ...
- **Home Assistant:** hass_control_light, hass_control_device, hass_read_sensor, ...
- **Delegation:** delegate_to_opus, google_deep_research

Tool visibility is configurable via `MCP_DISABLED_TOOLS` and `MCP_DISABLED_CATEGORIES` env vars.

---

## ⚡ Native C++ Module

Performance-critical operations via C++17 + pybind11 + SIMD (AVX2/NEON):

```
backend/native/src/
  axnmihn_native.cpp      # pybind11 bindings
  decay.cpp/.hpp           # Memory decay (SIMD batch)
  vector_ops.cpp/.hpp      # Cosine similarity, duplicate detection
  string_ops.cpp/.hpp      # Levenshtein distance
  graph_ops.cpp/.hpp       # BFS traversal
  text_ops.cpp/.hpp        # Text processing
```

All call sites fall back to pure Python if the module is not installed.

```bash
cd backend/native && pip install .
# Requires: CMake 3.18+, C++17 compiler, pybind11
```

---

## ⚙️ Configuration

### Environment Variables (`.env`)

```bash
# LLM Providers
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=                     # TTS fallback
TAVILY_API_KEY=                     # Search
DEEPGRAM_API_KEY=                   # STT

# Models
DEFAULT_GEMINI_MODEL=gemini-3-flash-preview
CHAT_MODEL=gemini-3-flash-preview
ANTHROPIC_CHAT_MODEL=claude-sonnet-4-5-20250929
ANTHROPIC_THINKING_BUDGET=10000
EMBEDDING_MODEL=models/gemini-embedding-001
EMBEDDING_DIMENSION=3072

# Server
HOST=0.0.0.0
PORT=8000
AXNMIHN_API_KEY=                    # API authentication
TZ=America/Vancouver

# PostgreSQL (optional - set to enable PG mode)
DATABASE_URL=postgresql://user:pass@localhost:5432/db
PG_POOL_MIN=2
PG_POOL_MAX=10

# Memory Budgets (chars)
BUDGET_SYSTEM_PROMPT=20000
BUDGET_TEMPORAL=5000
BUDGET_WORKING_MEMORY=80000
BUDGET_LONG_TERM=30000
BUDGET_GRAPHRAG=12000
BUDGET_SESSION_ARCHIVE=8000

# Memory Decay
MEMORY_BASE_DECAY_RATE=0.001
MEMORY_MIN_RETENTION=0.3
MEMORY_DECAY_DELETE_THRESHOLD=0.03
MEMORY_SIMILARITY_THRESHOLD=0.90
MEMORY_MIN_IMPORTANCE=0.25

# Context
CONTEXT_WORKING_TURNS=20
CONTEXT_FULL_TURNS=6
CONTEXT_MAX_CHARS=500000

# TTS
TTS_SERVICE_URL=http://127.0.0.1:8002
TTS_SYNTHESIS_TIMEOUT=30.0

# Home Assistant
HASS_URL=http://homeassistant.local:8123
HASS_TOKEN=
```

---

## 🚀 Quick Start

### Option A: Docker (Recommended)

```bash
git clone https://github.com/NorthProt-Inc/axnmihn.git
cd axnmihn

cp .env.example .env
# Edit .env with API keys

docker compose up -d

# Verify
curl http://localhost:8000/health/quick
```

This starts: backend (8000) + MCP (8555) + research (8766) + PostgreSQL (5432) + Redis (6379).

### Option B: Local Development

```bash
git clone https://github.com/NorthProt-Inc/axnmihn.git
cd axnmihn

python3.12 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

cp .env.example .env
# Edit .env with API keys

# (Optional) Native C++ module
cd backend/native && pip install . && cd ../..

# (Optional) Playwright for research
playwright install chromium

# (Optional) PostgreSQL + Redis
docker compose up -d postgres redis

# Run
uvicorn backend.app:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```

---

## 🐳 Deployment

### Docker Compose (Full Stack)

```bash
docker compose up -d              # Start all services
docker compose ps                 # Status
docker compose logs backend -f    # Follow backend logs
docker compose down               # Stop all
```

| Service | Port | Image/Target | Resources |
|---------|------|-------------|-----------|
| `backend` | 8000 | Dockerfile → runtime | 4G RAM, 2 CPU |
| `mcp` | 8555 | Dockerfile → runtime | 1G RAM, 1 CPU |
| `research` | 8766 | Dockerfile → research | 2G RAM, 1.5 CPU |
| `postgres` | 5432 | pgvector/pgvector:pg17 | - |
| `redis` | 6379 | redis:7-alpine (256MB) | - |

TTS (GPU-dependent) is commented out in docker-compose.yml. Uncomment if NVIDIA GPU is available.

### Systemd Services (Bare Metal)

| Service | Port | Purpose | Resources |
|---------|------|---------|-----------|
| `axnmihn-backend` | 8000 | FastAPI backend | 4G RAM, 200% CPU |
| `axnmihn-mcp` | 8555 | MCP server (SSE) | 1G RAM, 100% CPU |
| `axnmihn-research` | 8766 | Research MCP | 2G RAM, 150% CPU |
| `axnmihn-tts` | 8002 | TTS microservice (Qwen3-TTS) | 4G RAM, 200% CPU |
| `axnmihn-wakeword` | - | Wakeword detection | 512M RAM, 50% CPU |
| `context7-mcp` | 3002 | Context7 MCP | 1G RAM |
| `markitdown-mcp` | 3001 | Markitdown MCP | 1G RAM |

See [OPERATIONS.md](OPERATIONS.md) for detailed operations guide.

### Maintenance

| Script | Purpose |
|--------|---------|
| `scripts/memory_gc.py` | Memory garbage collection (dedup, decay, oversized removal) |
| `scripts/db_maintenance.py` | SQLite VACUUM, ANALYZE, integrity check |
| `scripts/dedup_knowledge_graph.py` | Knowledge graph deduplication |
| `scripts/regenerate_persona.py` | 7-day incremental persona update |
| `scripts/optimize_memory.py` | 4-phase memory optimization (text cleaning, role normalization) |
| `scripts/cleanup_messages.py` | LLM-powered message cleanup (parallel, checkpointed) |
| `scripts/populate_knowledge_graph.py` | Knowledge graph initial population |
| `scripts/night_ops.py` | Automated night shift research |
| `scripts/run_migrations.py` | Database schema migrations |

---

## 📁 Project Structure

```
axnmihn/
├── backend/
│   ├── app.py                    # FastAPI entry point, lifespan
│   ├── config.py                 # All configuration
│   ├── api/                      # HTTP routers (status, chat, memory, mcp, media, audio, openai)
│   ├── core/                     # Core services
│   │   ├── chat_handler.py       # Message routing
│   │   ├── context_optimizer.py  # Context size management
│   │   ├── mcp_client.py        # MCP client
│   │   ├── mcp_server.py        # MCP server setup
│   │   ├── health/              # Health monitoring
│   │   ├── identity/            # AI persona (ai_brain.py)
│   │   ├── intent/              # Intent classification
│   │   ├── logging/             # Structured logging
│   │   ├── mcp_tools/           # Tool implementations
│   │   ├── persona/             # Channel adaptation
│   │   ├── resilience/          # Circuit breaker, fallback
│   │   ├── security/            # Prompt defense
│   │   ├── session/             # Session state
│   │   ├── telemetry/           # Interaction logging
│   │   └── utils/               # Cache, retry, HTTP pool, Gemini client
│   ├── llm/                     # LLM providers (Gemini, Anthropic)
│   ├── media/                   # TTS manager
│   ├── memory/                  # 6-layer memory system
│   │   ├── unified.py           # MemoryManager orchestrator
│   │   ├── event_buffer.py      # M0: Event buffer
│   │   ├── current.py           # M1: Working memory
│   │   ├── recent/              # M3: Session archive (SQLite)
│   │   ├── permanent/           # M4: Long-term (ChromaDB)
│   │   ├── memgpt.py            # M5.1: Budget selection
│   │   ├── graph_rag.py         # M5.2: Knowledge graph
│   │   ├── meta_memory.py       # M5.3: Access tracking
│   │   ├── temporal.py          # Time context
│   │   └── pg/                  # PostgreSQL backend (optional)
│   ├── native/                  # C++17 extension module
│   ├── protocols/mcp/           # MCP protocol handlers
│   └── wake/                    # Wakeword + voice conversation
├── tests/                       # pytest suite
├── scripts/                     # Automation scripts
├── data/                        # Runtime data (SQLite, ChromaDB, JSON)
├── logs/                        # Application logs
├── storage/                     # Research artifacts, cron reports
├── Dockerfile                   # Multi-stage (runtime + research)
├── docker-compose.yml           # Full stack (app + PG + Redis)
├── .dockerignore
├── pyproject.toml               # Project metadata
└── .env                         # Environment configuration
```

---

## 📚 Documentation

- [OPERATIONS.md](OPERATIONS.md) — Operations guide (KR/EN)
- [AGENTS.md](AGENTS.md) — Custom agent definitions
- [logging.md](logging.md) — Logging system documentation
- [backend/native/README.md](backend/native/README.md) — C++ native module
- `.github/instructions/` — Development guidelines (TDD, security, performance, error analysis)

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

**Commit Convention:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, etc.)

**Code Style:**
- Python: `black` formatting, `ruff` linting, type hints required
- Max 400 lines per function, 800 lines per file
- Protocol-based interfaces, dataclass/pydantic data
- Prefer async def (I/O-bound operations)

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

---

## 🙏 Acknowledgments

- **FastAPI** — Modern web framework
- **ChromaDB** — Vector database
- **Anthropic & Google** — LLM APIs
- **Deepgram** — Speech recognition
- **Model Context Protocol** — Tool integration standard

---

**Made by:** NorthProt Inc.  
**Contact:** [GitHub Issues](https://github.com/NorthProt-Inc/axnmihn/issues)

</details>
