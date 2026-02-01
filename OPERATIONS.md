# Axnmihn Operations Guide

> **환경:** Pop!_OS (Ubuntu 24.04 LTS) + Systemd
> **대상:** Mark (종민)
> **마지막 업데이트:** 2026-02-01

---

## 목차

1. [서비스 구조](#서비스-구조)
2. [기초 생존 명령어](#기초-생존-명령어)
3. [파일 & 디렉토리 조작](#파일--디렉토리-조작)
4. [프로세스 & 서비스 관리](#프로세스--서비스-관리)
5. [Git 버전 관리](#git-버전-관리)
6. [Python 환경 관리](#python-환경-관리)
7. [Container 관리](#container-관리)
8. [디버깅 & 문제 해결](#디버깅--문제-해결)
9. [Axel 시스템 전용 명령어](#axel-시스템-전용-명령어)
10. [응급 상황 대응](#응급-상황-대응)
11. [빠른 참조 카드](#빠른-참조-카드)

---

## 서비스 구조

### Systemd User Services (Python/axnmihn)
> **참고:** 모든 서비스는 **user service**로 `systemctl --user`로 관리 (sudo 불필요)

| 서비스 | 포트 | 설명 |
|--------|------|------|
| axnmihn-backend.service | 8000 | Main FastAPI Backend |
| axnmihn-mcp.service | 8555 | MCP Server (SSE) |
| axnmihn-research.service | 8765 | Research MCP Server |
| axnmihn-wakeword.service | - | Wakeword Detector |
| northprot-containers.service | - | All Podman Containers |
| axel-sleep.service | - | Sleep Cycle (데이터 추출 + LoRA) |
| auto-cleanup.service | - | Weekly Auto Cleanup |

### Docker/Podman Containers (인프라)
| 컨테이너 | 포트 | 설명 |
|----------|------|------|
| homeassistant | 8123 | Home Automation |
| cloudflared | - | Main Tunnel |
| cloudflared-hass | - | HASS Tunnel |
| cloudflared-ssh | - | SSH Tunnel |
| axnmihn-frontend | 3080 | Frontend (Open WebUI) |
| axnmihn-mongodb | 27017 | MongoDB |
| axnmihn-meilisearch | 7700 | Meilisearch |

### 설정 파일 위치
```
/home/northprot/
├── .claude/                    # Claude Code 전역 설정
│   ├── settings.json
│   └── settings.local.json
├── projects/axnmihn/           # 프로젝트
│   ├── .claude/                # 프로젝트별 Claude 설정
│   │   └── settings.local.json
│   ├── .env                    # 환경변수
│   └── .mcp.json               # MCP 서버 설정
└── projects-env/                # Python venv (프로젝트 외부)
```

### Systemd 서비스 파일 위치
```
~/.config/systemd/user/           # User Services (sudo 불필요)
├── axnmihn-backend.service       # 메인 백엔드
├── axnmihn-mcp.service
├── axnmihn-research.service
├── axnmihn-wakeword.service
├── northprot-containers.service  # 모든 Podman 컨테이너
├── axel-sleep.service            # 수면 주기 (LoRA 훈련)
└── auto-cleanup.service          # 주간 자동 정리
```

---

## 기초 생존 명령어

### 현재 위치 & 이동
```bash
pwd                              # 지금 어디에 있는지
cd /home/northprot/projects/axnmihn  # 절대 경로로 이동
cd ..                            # 상위 폴더로
cd ~                             # 홈 디렉토리로
cd -                             # 이전 디렉토리로 돌아가기
```

### 파일/폴더 목록 보기
```bash
ls                     # 기본 목록
ls -la                 # 상세 목록 (숨김 파일 포함, 권한, 크기)
ls -lh                 # 사람이 읽기 쉬운 크기 (K, M, G)
ls -lt                 # 수정 시간순 정렬
```

### 파일 내용 보기
```bash
cat file.txt           # 전체 내용 출력
head -n 20 file.txt    # 처음 20줄
tail -n 20 file.txt    # 마지막 20줄
tail -f file.txt       # 실시간 파일 변화 모니터링 (로그 볼 때!)
less file.txt          # 페이지 단위로 보기 (q로 종료)
```

### 텍스트 검색
```bash
grep "검색어" file.txt              # 파일 내 검색
grep -r "검색어" .                  # 하위 폴더까지 재귀 검색
grep -rn "검색어" .                 # 재귀 검색 + 줄 번호
grep -i "검색어" file.txt           # 대소문자 무시
```

---

## 파일 & 디렉토리 조작

### 파일/폴더 생성
```bash
touch newfile.txt               # 빈 파일 생성
mkdir newfolder                 # 폴더 생성
mkdir -p a/b/c                  # 중첩 폴더 한 번에 생성
```

### 복사 & 이동
```bash
cp source.txt dest.txt          # 파일 복사
cp -r sourcedir/ destdir/       # 폴더 복사 (재귀)
mv old.txt new.txt              # 이름 변경 또는 이동
```

### 삭제 (주의!)
```bash
rm file.txt                     # 파일 삭제 (휴지통 없음!)
rm -r folder/                   # 폴더 삭제
rm -rf folder/                  # 강제 삭제 (물어보지 않음) - 위험!
```

> **CAUTION:** `rm -rf`는 되돌릴 수 없음! 특히 `rm -rf /` 또는 `rm -rf ~`는 시스템 파괴.
> 항상 삭제 전에 `ls`로 확인하고, 가능하면 `rm -ri`로 하나씩 확인.

### 파일 권한
```bash
chmod +x script.sh              # 실행 권한 추가
chmod 755 script.sh             # rwxr-xr-x (주인 모든 권한, 나머지 읽기+실행)
chmod 644 file.txt              # rw-r--r-- (주인 읽기쓰기, 나머지 읽기만)
```

---

## 프로세스 & 서비스 관리

### 프로세스 확인
```bash
ps aux                          # 모든 프로세스
ps aux | grep python            # Python 프로세스만
pgrep -a python                 # 파이썬 관련 프로세스 깔끔하게 나열
htop                            # 대화형 프로세스 모니터
top                             # 기본 모니터
```

### 프로세스 종료
```bash
kill PID                        # 정상 종료 요청
kill -9 PID                     # 강제 종료 (안 죽을 때)
pkill -f "uvicorn"              # 이름으로 종료
pkill -f [파일명.py]            # 부드러운 종료 (저장 등 마무리 기회)
pkill -9 -f [파일명.py]         # 강제 종료 (말 안 들을 때)
killall python                  # 모든 python 프로세스 종료
```

### 포트 확인 (매우 중요!)
```bash
lsof -i:8000                    # 8000 포트 사용 프로세스
lsof -i:8001                    # 8001 포트 확인
ss -tlnp                        # 모든 열린 포트 (현대적)
ss -tlnp | grep -E "8000|8555|8765|3080|8123"  # 주요 포트만
netstat -tlnp                   # 전통적인 포트 확인
```

> **TIP:** Axel 백엔드가 안 뜰 때 99%는 **포트 충돌**! 먼저 `lsof -i:포트번호`로 확인.

### Systemd 서비스 관리 (User Services)
> **중요:** User service는 `systemctl --user`로 관리 (sudo 사용 X)

```bash
# 상태 확인
systemctl --user status axnmihn-backend
systemctl --user status axnmihn-backend axnmihn-mcp axnmihn-research

# 시작/중지/재시작
systemctl --user start axnmihn-backend
systemctl --user stop axnmihn-backend
systemctl --user restart axnmihn-backend

# 전체 재시작
systemctl --user restart axnmihn-backend axnmihn-mcp axnmihn-research

# 부팅 시 자동 시작
systemctl --user enable axnmihn-backend
systemctl --user disable axnmihn-backend
```

### 로그 확인
```bash
# Systemd 저널 (user service는 --user 플래그 필요)
journalctl --user -u axnmihn-backend -f                    # 실시간 팔로우
journalctl --user -u axnmihn-backend -n 100                # 최근 100줄
journalctl --user -u axnmihn-backend --since "1 hour ago"  # 최근 1시간
journalctl --user -u axnmihn-mcp -f --since "10 min ago"

# 파일 로그 (추천 - 더 상세함)
tail -f ~/projects/axnmihn/logs/backend.log          # 실시간 로그
tail -f ~/projects/axnmihn/logs/backend_error.log    # 에러만
```

---

## Git 버전 관리

### 기본 워크플로우
```bash
git status                      # 변경사항 확인 (항상 먼저!)
git diff                        # 변경 내용 상세 보기
git diff --staged               # 스테이징된 변경사항
```

### 변경사항 저장
```bash
git add file.txt                # 특정 파일 스테이징
git add .                       # 모든 변경사항 스테이징
git commit -m "메시지"          # 커밋
git commit -am "메시지"         # add + commit 한 번에 (추적 중인 파일만)
```

### 히스토리 & 되돌리기
```bash
git log --oneline -10           # 최근 10개 커밋 한 줄씩
git log -p -1                   # 마지막 커밋 상세 diff

git checkout -- file.txt        # 파일 변경 취소 (커밋 전)
git reset HEAD~1                # 마지막 커밋 취소 (변경사항 유지)
git reset --hard HEAD~1         # 마지막 커밋 완전 삭제 (위험!)
```

### 브랜치
```bash
git branch                      # 브랜치 목록
git checkout -b feature-name    # 새 브랜치 생성 + 이동
git checkout main               # main 브랜치로 이동
git merge feature-name          # 브랜치 병합
```

### 원격 저장소
```bash
git pull                        # 원격에서 가져오기
git push                        # 원격으로 보내기
git remote -v                   # 원격 저장소 확인
```

### GitHub CLI
```bash
# 설치 & 인증
sudo apt install -y gh
gh auth login --web

# Git 설정
git config --global user.email "admin@northprot.com"
git config --global user.name "NorthProt"
git config --global init.defaultBranch main

# Repo 생성 & 푸시
gh repo create NorthProt-Inc/repo-name --public --source=. --remote=origin --push
```

---

## Python 환경 관리

### 시스템 Python & venv
```bash
# 시스템 Python (Ubuntu 24.x 기본)
/usr/bin/python3                # Python 3.12.3

# 프로젝트 venv (프로젝트 외부에 위치)
/home/northprot/projects-env/bin/python
/home/northprot/projects-env/bin/pip

# venv 활성화 (중요!)
source ~/projects-env/bin/activate
deactivate                      # 비활성화
```

### 패키지 관리
```bash
pip install package             # 패키지 설치
pip install -r backend/requirements.txt # 의존성 일괄 설치
pip freeze > backend/requirements.txt   # 현재 패키지 목록 저장
pip list                        # 설치된 패키지 목록
pip show package                # 패키지 정보
pip uninstall package           # 패키지 삭제

# 의존성 업데이트 원라이너
source ~/projects-env/bin/activate && cd /home/northprot/projects/axnmihn && pip install -r backend/requirements.txt --upgrade
```

### 코드 검증
```bash
python -m py_compile file.py    # 문법 검사 (실행 안 함)
python -c "import module"       # 모듈 import 테스트
python file.py                  # 실행
which python                    # 어떤 Python인지 확인
```

> **IMPORTANT:** 가상환경 활성화 안 하고 `pip install`하면 시스템 Python에 설치됨!
> 항상 `which python`으로 어떤 Python인지 확인.

---

## Container 관리

### Podman 기본 명령어
```bash
podman ps                       # 실행 중인 컨테이너
podman images                   # 이미지 목록
```

### 컨테이너 조작
```bash
podman start container_name     # 시작
podman stop container_name      # 중지
podman restart container_name   # 재시작
podman logs container_name      # 로그 보기
podman logs -f container_name   # 로그 실시간 팔로우
```

### Axel 컨테이너들
```bash
# 개별 재시작
podman restart axnmihn-frontend
podman restart mongodb
podman restart meilisearch
podman restart cloudflared

# 전체 재시작
podman restart meilisearch mongodb axnmihn-frontend cloudflared
```

### 컨테이너 내부 접속
```bash
podman exec -it container_name /bin/bash    # 컨테이너 쉘 접속
podman exec -it mongodb mongosh             # MongoDB 직접 접속
```

### Docker 관리 (호환)
```bash
docker ps -a                    # 모든 컨테이너
docker logs -f axnmihn-frontend # 로그
docker restart axnmihn-frontend # 재시작
```

---

## 디버깅 & 문제 해결

### 디스크 사용량
```bash
df -h                           # 전체 디스크 사용량
du -sh *                        # 현재 폴더 내 크기
du -sh * | sort -h              # 크기순 정렬
ncdu                            # 대화형 디스크 분석 (설치 필요)
```

### 메모리 & CPU
```bash
free -h                         # 메모리 사용량
watch -n 1 nvidia-smi           # 1초마다 GPU 모니터링

# 시스템 전체 모니터링 (CPU, RAM, GPU, 온도)
watch -n 1 'echo "=== CPU ===" && top -bn1 | head -5 && echo "" && echo "=== RAM ===" && free -h && echo "" && echo "=== GPU ===" && nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu --format=csv'
```

### GPU 관리
```bash
nvidia-smi                      # GPU 상태 확인
watch -n 1 nvidia-smi           # GPU 상태 실시간 모니터링
sudo nvidia-smi -pl 350         # Power Limit 350W로 올리기
```

### 네트워크
```bash
ping google.com                 # 인터넷 연결 확인
curl -I https://api.example.com # HTTP 헤더만 확인
curl https://api.example.com    # API 호출 테스트
```

### OpenRGB (RGB 조명)
```bash
which openrgb                    # 설치 확인
sudo openrgb --mode off          # 끄기
openrgb --color 000000           # 특정 색으로
```

---


## Axel 시스템 전용 명령어

### 핵심 디렉토리
```bash
/home/northprot/projects/axnmihn/              # 메인 코드
/home/northprot/projects/axnmihn/data/         # 데이터
/home/northprot/projects/axnmihn/logs/         # 로그
/home/northprot/.claude/                       # Claude Code 설정
```

### 백엔드 재시작 & 로그
```bash
# 재시작 + 로그 팔로우 (원라이너) - 추천!
systemctl --user restart axnmihn-backend && tail -f ~/projects/axnmihn/logs/backend.log

# 개별 명령 (user service - sudo 불필요)
systemctl --user restart axnmihn-backend
journalctl --user -u axnmihn-backend -f
systemctl --user status axnmihn-backend
```

### MCP 서버 관리
```bash
# User service로 관리 (sudo 불필요)
systemctl --user status axnmihn-mcp      # 상태 확인
systemctl --user restart axnmihn-mcp     # 재시작
journalctl --user -u axnmihn-mcp -f      # 로그 확인
systemctl --user stop axnmihn-mcp        # 중지
systemctl --user disable axnmihn-mcp     # 자동 시작 비활성화

# MCP 서버 직접 실행
PYTHONPATH=/home/northprot/projects/axnmihn /home/northprot/projects-env/bin/python /home/northprot/projects/axnmihn/backend/core/mcp_server.py
```

### Memory GC 수동 실행
```bash
cd /home/northprot/projects/axnmihn
source ~/projects-env/bin/activate
python scripts/memory_gc.py check           # 상태만 확인
python scripts/memory_gc.py cleanup         # 가비지 정리
python scripts/memory_gc.py full --dry-run  # 전체 GC 시뮬레이션
python scripts/memory_gc.py full            # 전체 GC 실제 실행
```

### Persona 재생성
```bash
cd /home/northprot/projects/axnmihn
source ~/projects-env/bin/activate
python scripts/regenerate_persona.py
```

### 스크립트 목록

| 스크립트 | 설명 | 사용법 |
|----------|------|--------|
| memory_gc.py | 메모리 GC | `python scripts/memory_gc.py [check\|cleanup\|full] [--dry-run]` |
| night_ops.py | 야간 자율 학습 | cron으로 실행 |
| regenerate_persona.py | 페르소나 재생성 | `python scripts/regenerate_persona.py` |
| evolve_persona_24h.py | 24시간 진화 | cron으로 실행 |
| populate_knowledge_graph.py | 지식 그래프 생성 | `python scripts/populate_knowledge_graph.py` |
| dedup_knowledge_graph.py | 지식 그래프 중복 제거 | `python scripts/dedup_knowledge_graph.py` |
| db_maintenance.py | DB 유지보수 | `python scripts/db_maintenance.py` |
| cleanup_messages.py | 메시지 정리 (LLM 기반) | `python scripts/cleanup_messages.py [--dry-run] [--limit N]` |
| cron_memory_gc.sh | 메모리 GC cron | `./scripts/cron_memory_gc.sh` |
| cron_audio_cleanup.sh | 오디오/로그 캐시 정리 | `./scripts/cron_audio_cleanup.sh` |
| run_migrations.py | DB 마이그레이션 | `python scripts/run_migrations.py` |

### API 테스트
```bash
# 헬스체크
curl http://localhost:8000/health

# 채팅 API (OpenAI 호환)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemini","messages":[{"role":"user","content":"안녕"}]}'

# 메모리 검색
curl "http://localhost:8000/memory/search?query=test&limit=5"
```

### 전체 상태 한눈에 보기
```bash
# 서비스 + 컨테이너 + 포트 한 번에
echo "=== Services ===" && systemctl --user status axnmihn-backend axnmihn-mcp axnmihn-research --no-pager | grep -E "●|Active" && echo "" && echo "=== Containers ===" && podman ps --format "table {{.Names}}\t{{.Status}}" && echo "" && echo "=== Ports ===" && ss -tlnp | grep -E "8000|8555|8765|3080|8123"
```

### 로그 파일 목록
```
logs/axnmihn.log        # 통합 로그
logs/backend.log        # 백엔드 로그
logs/backend_error.log  # 백엔드 에러
logs/mcp.log            # MCP 서버 로그
logs/mcp_error.log      # MCP 에러
logs/research.log       # 리서치 로그
logs/wakeword_error.log # 웨이크워드 에러
```

---

## 응급 상황 대응

### 백엔드가 안 뜰 때
```bash
# 1. 로그 확인 (user service)
journalctl --user -u axnmihn-backend -n 100
tail -n 100 ~/projects/axnmihn/logs/backend.log

# 2. 포트 확인
lsof -i:8000
lsof -i:8001

# 3. 좀비 프로세스 정리
pkill -f uvicorn
pkill -f python

# 4. 재시작 (user service - sudo 불필요)
systemctl --user restart axnmihn-backend
```

### 포트 충돌 (Address already in use)
```bash
lsof -i:8000              # 누가 쓰고 있는지 확인
sudo kill -9 PID          # 해당 프로세스 종료
```

### 서비스 hang
```bash
systemctl --user stop axnmihn-backend
systemctl --user start axnmihn-backend
```

### 디스크 꽉 찼을 때
```bash
# 1. 큰 파일 찾기
du -sh /home/northprot/* | sort -h | tail -20

# 2. 로그 정리
sudo journalctl --vacuum-size=500M

# 3. Python 캐시 정리
find . -type d -name "__pycache__" -exec rm -rf {} +

# 4. pip 캐시 정리
pip cache purge
```

### 변경사항 되돌리기
```bash
git checkout -- file.txt       # 커밋 안 한 변경 취소
git checkout -- .              # 모든 변경 취소 (위험!)
git reset --hard HEAD          # 마지막 커밋으로 완전 복구 (더 위험!)
```

### 컨테이너 전체 재시작
```bash
podman restart meilisearch mongodb axnmihn-frontend cloudflared
```

### 시스템 재부팅 (최후의 수단)
```bash
sudo reboot
```

---

## 빠른 참조 카드

| 상황 | 명령어 |
|------|--------|
| 어디있지? | `pwd` |
| 뭐있지? | `ls -la` |
| 포트 누가 쓰지? | `lsof -i:8000` |
| 로그 보기 | `tail -f ~/projects/axnmihn/logs/backend.log` |
| 서비스 재시작 | `systemctl --user restart axnmihn-backend` |
| Git 상태 | `git status` |
| venv 활성화 | `source ~/projects-env/bin/activate` |
| 프로세스 죽이기 | `kill -9 PID` |
| 컨테이너 상태 | `podman ps` |
| GPU 상태 | `nvidia-smi` |

---

## 절대 하지 말 것

| 명령어 | 위험도 | 이유 |
|--------|--------|------|
| `rm -rf /` | CRITICAL | 시스템 전체 삭제 |
| `rm -rf ~` | CRITICAL | 홈 디렉토리 삭제 |
| `chmod 777` | HIGH | 보안 취약점 (모든 권한 오픈) |
| `pip install` (venv 없이) | MEDIUM | 시스템 Python 오염 |
| `git push -f` | HIGH | 원격 히스토리 덮어씀 |

---

## 수정 전 체크리스트

- [ ] `git status`로 현재 상태 확인
- [ ] 수정할 파일 백업 (큰 변경 시)
- [ ] 가상환경 활성화 확인 (`which python`)
- [ ] 서비스 중지 (`systemctl --user stop axnmihn-backend`)
- [ ] 수정 후 문법 검사 (`python -m py_compile`)
- [ ] 테스트 실행
- [ ] 서비스 재시작

---

> **문제가 생기면:**
> 1. 에러 메시지를 **그대로** 읽어라
> 2. 로그를 확인해라
> 3. 구글에 에러 메시지 복붙
> 4. Python traceback은 **아래에서 위로** 읽음 (가장 아래 줄이 실제 에러)

*"차분하게, 하나씩, 확인하면서."*
