#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  Daily Cleanup - Audio Cache, JSON, and Old Logs
# ═══════════════════════════════════════════════════════════════════════════
# Runs daily at 5 AM PST via cron.
#
# Setup: crontab -e
#   0 5 * * * /home/northprot/projects/axnmihn/scripts/cron_audio_cleanup.sh
# ═══════════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
AUDIO_DIR="$PROJECT_DIR/static/audio"
LOGS_DIR="$PROJECT_DIR/logs"
LOG_FILE="$PROJECT_DIR/data/logs/cleanup.log"

mkdir -p "$(dirname "$LOG_FILE")"

echo "" >> "$LOG_FILE"
echo "═══════════════════════════════════════════════════════════════════" >> "$LOG_FILE"
echo " Daily Cleanup Started: $(date -Iseconds)" >> "$LOG_FILE"

# 1. Audio .wav files (older than 1 day)
WAV_BEFORE=$(find "$AUDIO_DIR" -name "*.wav" -type f 2>/dev/null | wc -l)
find "$AUDIO_DIR" -name "*.wav" -type f -mtime +1 -delete 2>/dev/null || true
WAV_AFTER=$(find "$AUDIO_DIR" -name "*.wav" -type f 2>/dev/null | wc -l)
echo "  Audio WAV: deleted $((WAV_BEFORE - WAV_AFTER)) files" >> "$LOG_FILE"

# 2. Audio .json files (older than 1 day)
JSON_BEFORE=$(find "$AUDIO_DIR" -name "*.json" -type f 2>/dev/null | wc -l)
find "$AUDIO_DIR" -name "*.json" -type f -mtime +1 -delete 2>/dev/null || true
JSON_AFTER=$(find "$AUDIO_DIR" -name "*.json" -type f 2>/dev/null | wc -l)
echo "  Audio JSON: deleted $((JSON_BEFORE - JSON_AFTER)) files" >> "$LOG_FILE"

# 3. Old log files (older than 7 days)
LOG_BEFORE=$(find "$LOGS_DIR" -name "*.log" -type f 2>/dev/null | wc -l)
find "$LOGS_DIR" -name "*.log" -type f -mtime +7 -delete 2>/dev/null || true
LOG_AFTER=$(find "$LOGS_DIR" -name "*.log" -type f 2>/dev/null | wc -l)
echo "  Log files: deleted $((LOG_BEFORE - LOG_AFTER)) files (7+ days old)" >> "$LOG_FILE"

echo " Cleanup Complete: $(date -Iseconds)" >> "$LOG_FILE"
echo "═══════════════════════════════════════════════════════════════════" >> "$LOG_FILE"
