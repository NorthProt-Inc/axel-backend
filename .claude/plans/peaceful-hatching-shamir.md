# Plan: aichat 포크 → axel-chat 리브랜딩

## Context

현재 `scripts/axel_chat.py`는 Python + Rich 기반 CLI 채팅 도구로, SSE 스트리밍 깨짐, 멀티라인 미지원, 히스토리 검색 없음 등 기능이 열악하고 버그가 많다. [sigoden/aichat](https://github.com/sigoden/aichat) (Rust, 9.2k stars, MIT/Apache 2.0)을 포크하여 `axel-chat`으로 리브랜딩한다.

aichat은 `env!("CARGO_CRATE_NAME")`으로 모든 브랜딩을 동적 해석하므로, `Cargo.toml`의 `name` 하나만 바꾸면 바이너리명·config 경로·env var·로그파일이 자동으로 변경된다.

## Step 1: GitHub 포크 생성

```bash
gh repo fork sigoden/aichat --org NorthProt-Inc --clone=false --fork-name axel-chat
gh repo clone NorthProt-Inc/axel-chat ~/projects/axel-chat
cd ~/projects/axel-chat
git remote add upstream https://github.com/sigoden/aichat.git
git checkout -b feat/rebrand-axel-chat
```

## Step 2: Cargo.toml 리브랜딩

`Cargo.toml`에서 package 섹션 수정:

```toml
[package]
name = "axel-chat"          # was "aichat" → 바이너리명, config 경로 등 자동 변경
description = "Axel CLI Chat - Terminal interface for the Axel AI assistant"
homepage = "https://github.com/NorthProt-Inc/axel-chat"
repository = "https://github.com/NorthProt-Inc/axel-chat"
authors = ["sigoden <sigoden@gmail.com>", "NorthProt-Inc"]
```

**자동 변경 효과:**
- 바이너리: `axel-chat`
- Config dir: `~/.config/axel_chat/`
- Env var 접두사: `AXEL_CHAT_*`
- 로그: `axel_chat.log`

## Step 3: src/config/mod.rs — GitHub URL 2곳 수정

- config 생성 시 참조 URL: `sigoden/aichat` → `NorthProt-Inc/axel-chat`
- agent 생성 시 참조 URL: 동일하게 변경

## Step 4: config.example.yaml — Axel 백엔드 프리셋 추가

파일 상단에 기본 모델 및 클라이언트 설정 추가:

```yaml
model: openai-compatible:axel:axel

clients:
  - type: openai-compatible
    name: axel
    api_base: http://localhost:8000/v1
    models:
      - name: axel
        max_input_tokens: 2000000
        supports_vision: true
        supports_function_calling: false
```

## Step 5: README.md 리브랜딩

- 프로젝트명/설명을 axel-chat으로 변경
- upstream aichat 크레딧 명시
- Axel 백엔드 연동 방법 문서화

## Step 6: 빌드 & 설치

```bash
cd ~/projects/axel-chat
cargo build --release
cp target/release/axel-chat ~/.cargo/bin/
```

## Step 7: 기본 config 생성

`~/.config/axel_chat/config.yaml`:

```yaml
model: openai-compatible:axel:axel
stream: true
save: true
keybindings: emacs

clients:
  - type: openai-compatible
    name: axel
    api_base: http://localhost:8000/v1
    models:
      - name: axel
        max_input_tokens: 2000000
        supports_vision: true
        supports_function_calling: false
```

## Step 8: axnmihn 프로젝트 정리

- `scripts/axel_chat.py` 상단에 deprecation 안내 추가
- `OPERATIONS.md` 업데이트: `axel-chat` 사용법 안내

## Verification

```bash
axel-chat --version          # "axel-chat 0.30.0" 출력 확인
axel-chat -e "안녕"          # 단일 쿼리 → localhost:8000 응답 확인
axel-chat                    # REPL 모드 진입 → 스트리밍 대화 확인
axel-chat :models            # axel 모델 목록 확인
```

## Upstream 동기화

```bash
cd ~/projects/axel-chat
git fetch upstream && git merge upstream/main
# 충돌은 4개 파일(Cargo.toml, src/config/mod.rs, config.example.yaml, README.md)에만 발생
```
