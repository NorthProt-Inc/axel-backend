"""Tests for native text_ops module (Korean spacing correction)."""

import pytest

try:
    import axnmihn_native as native

    HAS_NATIVE = True
except ImportError:
    native = None
    HAS_NATIVE = False

pytestmark = pytest.mark.skipif(not HAS_NATIVE, reason="native module not built")


# ---------------------------------------------------------------------------
# Rule 1: .!? + Hangul -> insert space (except ellipsis)
# ---------------------------------------------------------------------------
class TestRule1SentenceEnd:
    def test_period_hangul(self):
        assert native.text_ops.fix_korean_spacing("이다.브라더") == "이다. 브라더"

    def test_exclamation_hangul(self):
        assert native.text_ops.fix_korean_spacing("좋아!정말") == "좋아! 정말"

    def test_question_hangul(self):
        assert native.text_ops.fix_korean_spacing("뭐야?그게") == "뭐야? 그게"

    def test_period_already_spaced(self):
        assert native.text_ops.fix_korean_spacing("이다. 브라더") == "이다. 브라더"

    def test_ellipsis_excluded(self):
        assert native.text_ops.fix_korean_spacing("그래서..이렇게") == "그래서..이렇게"

    def test_three_dot_ellipsis_excluded(self):
        assert native.text_ops.fix_korean_spacing("음...그래") == "음...그래"

    def test_period_ascii(self):
        """Period + ASCII should NOT insert space."""
        assert native.text_ops.fix_korean_spacing("e.g.this") == "e.g.this"


# ---------------------------------------------------------------------------
# Rule 2: ])} + Hangul -> insert space
# ---------------------------------------------------------------------------
class TestRule2CloseBracket:
    def test_square_bracket(self):
        assert native.text_ops.fix_korean_spacing("]브라더") == "] 브라더"

    def test_paren(self):
        assert native.text_ops.fix_korean_spacing(")한국어") == ") 한국어"

    def test_curly(self):
        assert native.text_ops.fix_korean_spacing("}데이터") == "} 데이터"

    def test_bracket_ascii(self):
        """Close bracket + ASCII should NOT insert space."""
        assert native.text_ops.fix_korean_spacing("]data") == "]data"


# ---------------------------------------------------------------------------
# Rule 3: Hangul + [({ -> insert space
# ---------------------------------------------------------------------------
class TestRule3OpenBracket:
    def test_hangul_square(self):
        assert native.text_ops.fix_korean_spacing("한글[System") == "한글 [System"

    def test_hangul_paren(self):
        assert native.text_ops.fix_korean_spacing("데이터(test)") == "데이터 (test)"

    def test_hangul_curly(self):
        assert native.text_ops.fix_korean_spacing("값{key}") == "값 {key}"

    def test_ascii_open_bracket(self):
        """ASCII + open bracket should NOT insert space."""
        assert native.text_ops.fix_korean_spacing("data[0]") == "data[0]"


# ---------------------------------------------------------------------------
# Rule 4: : + Hangul -> insert space
# ---------------------------------------------------------------------------
class TestRule4Colon:
    def test_colon_hangul(self):
        assert native.text_ops.fix_korean_spacing("Log:한글") == "Log: 한글"

    def test_colon_already_spaced(self):
        assert native.text_ops.fix_korean_spacing("Log: 한글") == "Log: 한글"

    def test_colon_ascii(self):
        assert native.text_ops.fix_korean_spacing("key:value") == "key:value"


# ---------------------------------------------------------------------------
# Rule 5: * + Hangul -> insert space (markdown bold)
# ---------------------------------------------------------------------------
class TestRule5Asterisk:
    def test_bold_hangul(self):
        assert (
            native.text_ops.fix_korean_spacing("**bold**한글") == "**bold** 한글"
        )

    def test_asterisk_already_spaced(self):
        assert (
            native.text_ops.fix_korean_spacing("**bold** 한글") == "**bold** 한글"
        )


# ---------------------------------------------------------------------------
# Rule 6: consecutive spaces -> single space
# ---------------------------------------------------------------------------
class TestRule6MultipleSpaces:
    def test_double_space(self):
        assert native.text_ops.fix_korean_spacing("hello  world") == "hello world"

    def test_triple_space(self):
        assert (
            native.text_ops.fix_korean_spacing("hello   world") == "hello world"
        )

    def test_mixed_spaces_and_rule(self):
        assert (
            native.text_ops.fix_korean_spacing("이다.  브라더") == "이다. 브라더"
        )


# ---------------------------------------------------------------------------
# Safety: no space inserted between two Hangul characters
# ---------------------------------------------------------------------------
class TestSafetyHangul:
    def test_hangul_hangul(self):
        assert native.text_ops.fix_korean_spacing("나는학생이다") == "나는학생이다"

    def test_particles_preserved(self):
        """Josa (particles) must not be separated."""
        assert native.text_ops.fix_korean_spacing("학교에서") == "학교에서"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_empty_string(self):
        assert native.text_ops.fix_korean_spacing("") == ""

    def test_pure_ascii(self):
        assert native.text_ops.fix_korean_spacing("hello world") == "hello world"

    def test_pure_korean(self):
        assert native.text_ops.fix_korean_spacing("안녕하세요") == "안녕하세요"

    def test_multiple_rules_combined(self):
        text = "결과.다음[항목]출력"
        expected = "결과. 다음 [항목] 출력"
        assert native.text_ops.fix_korean_spacing(text) == expected

    def test_newlines_preserved(self):
        text = "안녕\n세상"
        assert native.text_ops.fix_korean_spacing(text) == "안녕\n세상"


# ---------------------------------------------------------------------------
# Batch API
# ---------------------------------------------------------------------------
class TestBatch:
    def test_batch(self):
        texts = ["이다.브라더", "좋아!정말", "hello"]
        result = native.text_ops.fix_korean_spacing_batch(texts)
        assert result == ["이다. 브라더", "좋아! 정말", "hello"]

    def test_batch_empty_list(self):
        assert native.text_ops.fix_korean_spacing_batch([]) == []
