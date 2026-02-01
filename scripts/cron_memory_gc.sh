#!/bin/bash

set -euo pipefail

PROJECT_DIR="/home/northprot/projects/axnmihn"
VENV_DIR="/home/northprot/projects-env"
LOG_FILE="$PROJECT_DIR/data/logs/memory_gc.log"
LOCK_FILE="/tmp/axnmihn-memory-gc.lock"
TIMEOUT_SECONDS=1800
ADMIN_EMAIL="${AXNMIHN_ADMIN_EMAIL:-}"

mkdir -p "$(dirname "$LOG_FILE")"

timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

notify_error() {
    local message="$1"
    echo "[$(timestamp)] ERROR: $message" >> "$LOG_FILE"

    if [ -n "$ADMIN_EMAIL" ]; then
        echo "$message" | mail -s "ALERT: Axnmihn Memory GC Failed" "$ADMIN_EMAIL" 2>/dev/null || true
    fi

    # 로컬 알림 파일 생성
    mkdir -p "$PROJECT_DIR/data/alerts"
    echo "[$(timestamp)] $message" >> "$PROJECT_DIR/data/alerts/memory_gc_errors.log"
}

# 경로 검증
if [ ! -d "$PROJECT_DIR" ]; then
    notify_error "PROJECT_DIR not found: $PROJECT_DIR"
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    notify_error "VENV_DIR not found: $VENV_DIR"
    exit 1
fi

# Lock 획득 시도 (flock 사용)
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "[$(timestamp)] Another instance is running. Skipping." >> "$LOG_FILE"
    exit 0
fi

# 시작 로그
echo "" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "[$(timestamp)] Memory GC Started" >> "$LOG_FILE"

# venv 활성화
source "$VENV_DIR/bin/activate"
cd "$PROJECT_DIR"

# 실행 (타임아웃 적용)
START_TIME=$(date +%s)
if timeout "$TIMEOUT_SECONDS" python scripts/memory_gc.py full >> "$LOG_FILE" 2>&1; then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# 결과 로깅
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(timestamp)] Memory GC Completed (${DURATION}s)" >> "$LOG_FILE"
elif [ $EXIT_CODE -eq 124 ]; then
    notify_error "Memory GC TIMEOUT after ${TIMEOUT_SECONDS}s"
else
    notify_error "Memory GC FAILED with exit code $EXIT_CODE"
fi

echo "========================================" >> "$LOG_FILE"

# Lock 해제 (자동으로 해제되지만 명시적으로)
flock -u 200

exit $EXIT_CODE
