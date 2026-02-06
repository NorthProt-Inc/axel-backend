---
description: 모든 관련 서비스 상태 한눈에 확인
allowed-tools: [Bash]
---

# /services - 전체 서비스 상태

## 동작
Axnmihn 관련 서비스, 크론잡, 타이머의 상태를 한눈에 확인합니다.

## 확인 항목

### 1. Systemd 사용자 서비스 (axnmihn 관련)
```bash
systemctl --user list-units --type=service --state=running,failed,activating 2>/dev/null | grep -E "(axnmihn|mcp|wakeword|research|docker)" || echo "관련 서비스 없음"
```

### 2. Axnmihn 백엔드 상태
```bash
systemctl --user status axnmihn-backend --no-pager 2>/dev/null | head -10 || echo "axnmihn-backend 서비스 없음"
```

### 3. MCP 서버 상태
```bash
systemctl --user status axnmihn-mcp --no-pager 2>/dev/null | head -10 || echo "axnmihn-mcp 서비스 없음"
```

### 4. Research 서버 상태
```bash
systemctl --user status axnmihn-research --no-pager 2>/dev/null | head -10 || echo "axnmihn-research 서비스 없음"
```

### 5. Wakeword 서비스 상태
```bash
systemctl --user status axnmihn-wakeword --no-pager 2>/dev/null | head -10 || echo "wakeword 서비스 없음"
```

### 6. 포트 사용 현황
```bash
ss -tlnp 2>/dev/null | grep -E ":(8000|8001|8080|3000|5000|5173|9000)" || echo "관련 포트 미사용"
```

### 7. Python 프로세스
```bash
pgrep -af "python.*(axnmihn|uvicorn|mcp)" 2>/dev/null | head -10 || echo "관련 Python 프로세스 없음"
```

### 8. Systemd 타이머 (자동 실행)
```bash
systemctl --user list-timers --all 2>/dev/null | grep -E "(axnmihn|mcp|cleanup|review)" || echo "관련 타이머 없음"
```

### 9. 크론잡 목록
```bash
crontab -l 2>/dev/null || echo "크론탭 없음"
```

### 10. 디스크 사용량 (프로젝트 폴더)
```bash
du -sh ~/projects/axnmihn 2>/dev/null || echo "프로젝트 폴더 없음"
```

## 출력 형식
각 항목을 테이블 형식으로 정리:

### 서비스 상태
| 서비스 | 상태 | PID | 포트 | 메모리 |
|--------|------|-----|------|--------|

### Systemd 타이머
| 타이머 | 다음 실행 | 주기 | 설명 |
|--------|----------|------|------|

### 크론잡
| 시간 | 스크립트 | 설명 |
|------|----------|------|

## 관련 명령어
- `/restart` - 백엔드 재시작
- `/logs` - 로그 확인
- `/analyze-error` - 에러 분석
