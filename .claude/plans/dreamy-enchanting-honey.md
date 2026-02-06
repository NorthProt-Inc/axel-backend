# Korean Spacing Correction: C++ Native Module + Migration Script

## Context
어시스턴트 응답의 한국어 띄어쓰기 오류가 ChromaDB(974개)와 working_memory.json(60개)에 그대로 저장되어 피드백 루프를 형성하고 있다. 기존 native C++ 모듈에 `text_ops` 서브모듈을 추가하고, 저장된 메모리의 띄어쓰기를 일괄 수정하는 스크립트를 만든다.

## New Files (4개)

| File | Purpose |
|------|---------|
| `backend/native/src/text_ops.hpp` | 한국어 띄어쓰기 수정 함수 선언 |
| `backend/native/src/text_ops.cpp` | C++ 구현 (UTF-8 → codepoints → rule-based fix → UTF-8) |
| `backend/native/tests/test_text_ops.py` | 테스트 |
| `scripts/fix_spacing.py` | ChromaDB + working_memory.json 일괄 수정 스크립트 |

## Modified Files (2개)

| File | Change |
|------|--------|
| `backend/native/CMakeLists.txt:41` | `src/text_ops.cpp` 추가 |
| `backend/native/src/axnmihn_native.cpp` | `#include "text_ops.hpp"` + pybind11 `text_ops` 서브모듈 바인딩 |

## C++ Module: `text_ops`

### API
```
axnmihn_native.text_ops.fix_korean_spacing(text: str) -> str
axnmihn_native.text_ops.fix_korean_spacing_batch(texts: list[str]) -> list[str]
```

### Algorithm
UTF-8 → `vector<uint32_t>` codepoints → single-pass rule application → UTF-8

### Spacing Rules (punctuation/bracket 경계만 — 항상 안전)

| # | Rule | Example |
|---|------|---------|
| 1 | `.!?` + 한글 → 공백 삽입 (말줄임표 `..` 제외) | `이다.브라더` → `이다. 브라더` |
| 2 | `])}` + 한글 → 공백 삽입 | `]브라더` → `] 브라더` |
| 3 | 한글 + `[({` → 공백 삽입 | `한글[System` → `한글 [System` |
| 4 | `:` + 한글 → 공백 삽입 | `Log:한글` → `Log: 한글` |
| 5 | `*` + 한글 → 공백 삽입 (markdown bold) | `**bold**한글` → `**bold** 한글` |
| 6 | 연속 공백 → 단일 공백 | `hello   world` → `hello world` |

**안전 보장**: 한글↔한글 사이에는 공백을 삽입하지 않음 (조사 보호)

### Hangul Detection
```cpp
bool is_korean(uint32_t cp) {
    return (cp >= 0xAC00 && cp <= 0xD7AF) ||   // Hangul Syllables
           (cp >= 0x1100 && cp <= 0x11FF) ||     // Hangul Jamo
           (cp >= 0x3130 && cp <= 0x318F);       // Compat Jamo
}
```

## Migration Script: `scripts/fix_spacing.py`

```
python scripts/fix_spacing.py              # dry-run (미리보기)
python scripts/fix_spacing.py --apply      # 실제 적용
python scripts/fix_spacing.py --target wm  # working_memory.json만
python scripts/fix_spacing.py --target chroma  # ChromaDB만
```

- Native C++ 사용, 없으면 Python fallback
- ChromaDB: `collection.update(ids=..., documents=...)` — 임베딩 재생성 불필요 (의미 변화 없음)
- working_memory.json: `messages[*].content` 필드만 수정
- 변경 전 diff preview 표시

## Implementation Order

1. `text_ops.hpp` + `text_ops.cpp` 작성
2. `CMakeLists.txt` + `axnmihn_native.cpp` 수정
3. 빌드: `cd backend/native && pip install .`
4. `test_text_ops.py` 작성 및 실행
5. `scripts/fix_spacing.py` 작성
6. dry-run → 확인 → `--apply`

## Verification
```bash
# 1. 빌드 확인
python -c "import axnmihn_native; print(axnmihn_native.text_ops.fix_korean_spacing('이다.브라더'))"
# Expected: "이다. 브라더"

# 2. 테스트
pytest backend/native/tests/test_text_ops.py -v

# 3. dry-run
python scripts/fix_spacing.py

# 4. 적용
python scripts/fix_spacing.py --apply
```
