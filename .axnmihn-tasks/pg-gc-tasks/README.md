# PG Memory GC Tasks

**Generated**: 2026-02-11
**Scope**: PostgreSQL 기반 메모리 시스템 GC 스크립트 구현
**Total tasks**: 3 (GC-001, GC-002, INTEGRATION-VERIFY)

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| HIGH | 1 | GC 스크립트 본체 + 테스트 (8 phases 번들) |
| MEDIUM | 1 | Cron wrapper 스크립트 |
| CRITICAL | 1 | 통합 검증 |

## Dependency Graph

```
Wave 1 (2 parallel slots)
  ├── GC-001  pg_memory_gc.py + tests (Phase 1-8 bundle)
  └── GC-002  cron_pg_gc.sh wrapper
       ↓
Wave 2 (1 slot)
  └── INTEGRATION-VERIFY  통합 검증
```

## File Conflict Bundles

| Bundle | Files | Reason |
|--------|-------|--------|
| GC-001 | `scripts/pg_memory_gc.py`, `tests/scripts/test_pg_memory_gc.py` | Phase 1-8 모두 단일 스크립트에 구현 |

## Wave Execution Plan

| Wave | Tasks | Agent Slots | Est. Time |
|------|-------|-------------|-----------|
| 1 | 2 | 2 parallel | ~40 min |
| 2 | 1 | 1 sequential | ~10 min |

## Task File Index

### Wave 1 — Implementation
- [`GC-001`](wave-1/GC-001-pg-memory-gc-script-bundle.md) — PG Memory GC 스크립트 + 테스트
- [`GC-002`](wave-1/GC-002-cron-wrapper.md) — Cron wrapper 스크립트

### Wave 2 — Integration
- [`INTEGRATION-VERIFY`](wave-2/INTEGRATION-VERIFY.md) — 통합 검증

## Execution Instructions

```bash
# Wave 1: GC-001과 GC-002를 병렬 실행
# GC-001: TDD 순서로 Phase 1→2→3→4→5-7→8 구현
# GC-002: cron wrapper 작성 (독립)

# Wave 2: Wave 1 완료 후 통합 검증
ruff check scripts/pg_memory_gc.py
python -m pytest tests/scripts/test_pg_memory_gc.py -v
python scripts/pg_memory_gc.py check
python scripts/pg_memory_gc.py --dry-run
bash -n scripts/cron_pg_gc.sh
```
