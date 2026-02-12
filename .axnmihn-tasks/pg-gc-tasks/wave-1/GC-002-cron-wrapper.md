# GC-002: Cron Wrapper Script

## Metadata
| Field | Value |
|-------|-------|
| ID | GC-002 |
| Severity | MEDIUM |
| File | Create: `scripts/cron_pg_gc.sh` |
| Wave | 1 |
| Depends On | (none) |
| Blocks | INTEGRATION-VERIFY |

## Context
`scripts/cron_memory_gc.sh` 패턴을 따라 PG GC용 cron wrapper 작성. Lock file로 중복 실행 방지, 로그 로테이션, 에러 알림 파일 생성.

## Reference
- `scripts/cron_memory_gc.sh` — 기존 cron wrapper 패턴

## Changes from Reference
| Item | Old (ChromaDB) | New (PG) |
|------|----------------|----------|
| LOCK_FILE | `/tmp/axnmihn-memory-gc.lock` | `/tmp/axnmihn-pg-memory-gc.lock` |
| LOG_FILE | `$PROJECT_DIR/data/logs/memory_gc.log` | `$PROJECT_DIR/data/logs/pg_memory_gc.log` |
| Command | `python scripts/memory_gc.py full` | `python scripts/pg_memory_gc.py full` |
| Error log | `memory_gc_errors.log` | `pg_memory_gc_errors.log` |

## Implementation
- Lock file 기반 중복 실행 방지 (`flock` 또는 PID file)
- 로그 파일 로테이션 (크기 기반)
- 실행 시작/종료 타임스탬프 로깅
- 에러 시 별도 에러 로그 파일 생성
- Exit code 전파

## Acceptance Criteria
- [ ] `bash -n scripts/cron_pg_gc.sh` syntax check 통과
- [ ] Lock file로 중복 실행 방지
- [ ] 로그 파일에 실행 기록 남김
- [ ] 에러 시 에러 로그 생성
- [ ] `cron_memory_gc.sh`와 동일한 패턴 유지
