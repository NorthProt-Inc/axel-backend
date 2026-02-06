---
description: 백엔드 재시작 후 헬스체크 수행
allowed-tools: [Bash, mcp__axel-mcp__read_system_logs]
---

# /restart - 백엔드 재시작 및 헬스체크

## 동작
1. axel-backend 서비스 재시작 (systemctl --user restart)
2. 5초 대기 후 헬스체크 수행 (curl localhost:8000/health)
3. 서비스 상태 확인 (systemctl --user status)
4. 최근 로그 10줄 출력

## 실행 순서

### 1단계: 서비스 재시작
```bash
systemctl --user restart axel-backend
```

### 2단계: 대기 및 헬스체크
```bash
sleep 5 && curl -s http://localhost:8000/health | jq .
```

### 3단계: 서비스 상태 확인
```bash
systemctl --user status axel-backend --no-pager
```

### 4단계: 최근 로그 확인
MCP 도구 `mcp__axel-mcp__read_system_logs`를 사용하여 최근 로그 10줄 확인

## 성공 기준
- 헬스체크 응답이 200 OK
- 서비스 상태가 "active (running)"
- 로그에 에러 없음

## 실패 시
- 에러 로그 분석하여 원인 파악
- `/analyze-error` 명령어로 상세 분석 권장
