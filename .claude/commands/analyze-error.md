---
description: 최근 에러 분석 및 원인 추적
argument-hint: [lines=100]
allowed-tools: [Read, Grep, Bash, mcp__axel-mcp__read_system_logs, mcp__axel-mcp__analyze_log_errors]
---

# /analyze-error - 에러 로그 분석

## 사용법
- `/analyze-error` - 최근 100줄 분석
- `/analyze-error 500` - 최근 500줄 분석
- `/analyze-error backend_error.log` - 특정 로그 파일

## 인자: $ARGUMENTS
- 숫자: 분석할 로그 줄 수 (기본: 100)
- 파일명: 분석할 로그 파일 (기본: backend.log)

## 동작

### 1단계: 에러 로그 수집
MCP 도구 `mcp__axel-mcp__analyze_log_errors` 사용:
- lines: $ARGUMENTS 또는 500
- log_file: "backend.log"

### 2단계: 에러 패턴 분류
수집된 에러를 다음 카테고리로 분류:
- **연결 에러**: ConnectionError, TimeoutError
- **인증 에러**: AuthenticationError, 401, 403
- **데이터 에러**: ValidationError, JSONDecodeError
- **서버 에러**: 500, InternalServerError
- **기타**: 위 카테고리에 해당하지 않는 에러

### 3단계: 트레이스백 분석
에러 트레이스백에서 추출:
- 원인 파일 및 라인 번호
- 호출 스택
- 관련 함수/클래스

### 4단계: 원인 추적
관련 소스 코드 읽기 (해당 파일의 에러 발생 라인 주변)

## 출력 형식
```
## 에러 분석 리포트

### 요약
- 총 에러 수: N개
- 가장 빈번한 에러: ErrorType (M회)
- 마지막 에러 발생: YYYY-MM-DD HH:MM:SS

### 에러 유형별 분류
| 유형 | 횟수 | 최근 발생 |
|------|------|-----------|

### 상세 분석
#### 1. ErrorType (가장 빈번)
- 발생 위치: file.py:123
- 원인 추정: ...
- 해결 방안: ...

### 권장 조치
1. 첫 번째 조치
2. 두 번째 조치
```

## 관련 명령어
- `/logs error` - 에러 로그만 보기
- `/restart` - 서비스 재시작
