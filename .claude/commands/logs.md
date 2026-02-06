---
description: 백엔드 로그 확인 (error|warn|all|N줄)
argument-hint: [error|warn|all|숫자]
allowed-tools: [Bash, mcp__axel-mcp__read_system_logs, mcp__axel-mcp__analyze_log_errors]
---

# /logs - 로그 모니터링

## 사용법
- `/logs` - 최근 로그 50줄
- `/logs error` - 에러만 필터링
- `/logs warn` - 경고만 필터링
- `/logs 100` - 최근 100줄
- `/logs all` - 전체 로그 (최근 200줄)

## 인자: $ARGUMENTS

## 동작

### 인자가 없거나 숫자인 경우
MCP 도구 `mcp__axel-mcp__read_system_logs` 사용:
- lines: $ARGUMENTS (숫자) 또는 기본값 50
- log_file: "backend.log"

### 인자가 "error"인 경우
MCP 도구 `mcp__axel-mcp__read_system_logs` 사용:
- filter_keyword: "ERROR"
- lines: 100

### 인자가 "warn"인 경우
MCP 도구 `mcp__axel-mcp__read_system_logs` 사용:
- filter_keyword: "WARNING"
- lines: 100

### 인자가 "all"인 경우
MCP 도구 `mcp__axel-mcp__read_system_logs` 사용:
- lines: 200
- log_file: "backend.log"

## 출력 형식
- 타임스탬프, 레벨, 메시지 형식으로 정리
- 에러는 빨간색 강조 (터미널 지원 시)
- 중복 에러는 그룹화하여 카운트 표시

## 관련 명령어
- `/analyze-error` - 에러 패턴 분석
- `/restart` - 백엔드 재시작
