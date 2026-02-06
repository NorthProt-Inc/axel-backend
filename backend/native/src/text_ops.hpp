#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace axnmihn {
namespace text_ops {

/**
 * Check if a Unicode codepoint is a Korean (Hangul) character.
 *
 * Covers Hangul Syllables (AC00-D7AF), Jamo (1100-11FF),
 * and Compatibility Jamo (3130-318F).
 */
bool is_korean(uint32_t cp);

/**
 * Fix Korean spacing around punctuation and bracket boundaries.
 *
 * Rules applied (single pass):
 *   1. `.!?` + Hangul -> insert space (except ellipsis `..`)
 *   2. `])}` + Hangul -> insert space
 *   3. Hangul + `[({` -> insert space
 *   4. `:` + Hangul -> insert space
 *   5. `*` + Hangul -> insert space (markdown bold boundary)
 *   6. Consecutive spaces -> single space
 *
 * Safety: never inserts space between two Hangul characters.
 */
std::string fix_korean_spacing(const std::string& text);

/**
 * Batch version of fix_korean_spacing.
 */
std::vector<std::string> fix_korean_spacing_batch(
    const std::vector<std::string>& texts);

}  // namespace text_ops
}  // namespace axnmihn
