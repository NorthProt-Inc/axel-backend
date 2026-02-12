# INTEGRATION-VERIFY: PG Memory GC 통합 검증

## Metadata
| Field | Value |
|-------|-------|
| ID | INTEGRATION-VERIFY |
| Severity | CRITICAL |
| Wave | 2 (Final) |
| Depends On | GC-001, GC-002 |

## Verification Checklist

### 1. Lint
```bash
ruff check scripts/pg_memory_gc.py
```
- [ ] lint 위반 없음

### 2. Unit Tests
```bash
python -m pytest tests/scripts/test_pg_memory_gc.py -v
```
- [ ] 전체 테스트 통과
- [ ] Phase별 mock 테스트 통과
- [ ] dry-run 검증 테스트 통과

### 3. Check Mode (실제 DB)
```bash
python scripts/pg_memory_gc.py check
```
- [ ] 각 테이블 row count 정상 출력
- [ ] DB 연결 성공
- [ ] 에러 없이 종료

### 4. Dry-Run Mode (실제 DB)
```bash
python scripts/pg_memory_gc.py full --dry-run
```
- [ ] DRY-RUN 태그와 함께 각 phase 실행
- [ ] 실제 데이터 변경 없음
- [ ] 모든 phase 정상 완료

### 5. Cron Wrapper Syntax
```bash
bash -n scripts/cron_pg_gc.sh
```
- [ ] syntax 오류 없음

### 6. Phase별 검증
| Phase | Description | Verification |
|-------|-------------|-------------|
| 1 | Emoji strip | 이모지 포함 레코드 0개 확인 |
| 2 | LLM summarize | 2000자 초과 메시지 처리 확인 |
| 3 | Hash dedup | 중복 해시 0개 확인 |
| 4 | Decay cleanup | `decayed_importance < 0.1` 레코드 0개 확인 |
| 5 | Archive cleanup | 90일 초과 archived_messages 0개 확인 |
| 6 | Meta cleanup | 30일 초과 access_patterns 0개 확인 |
| 7 | KG cleanup | Orphan relations 0개 확인 |
| 8 | VACUUM | VACUUM ANALYZE 정상 실행 |

## Sign-off
- [ ] 모든 검증 항목 통과
- [ ] GC 스크립트 정상 동작 확인
- [ ] Cron wrapper 정상 동작 확인
