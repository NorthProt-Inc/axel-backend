#include "text_ops.hpp"

#include <cstddef>

namespace axnmihn {
namespace text_ops {

// ---------------------------------------------------------------------------
// UTF-8 helpers
// ---------------------------------------------------------------------------

namespace {

/// Decode one UTF-8 codepoint starting at `data[pos]`.
/// Advances `pos` past the consumed bytes and returns the codepoint.
/// On invalid input returns 0xFFFD (replacement char) and advances by 1.
inline uint32_t decode_utf8(const char* data, size_t len, size_t& pos) {
    auto byte = static_cast<uint8_t>(data[pos]);

    if (byte < 0x80) {
        pos += 1;
        return byte;
    }
    if ((byte & 0xE0) == 0xC0 && pos + 1 < len) {
        uint32_t cp = (byte & 0x1F) << 6;
        cp |= (static_cast<uint8_t>(data[pos + 1]) & 0x3F);
        pos += 2;
        return cp;
    }
    if ((byte & 0xF0) == 0xE0 && pos + 2 < len) {
        uint32_t cp = (byte & 0x0F) << 12;
        cp |= (static_cast<uint8_t>(data[pos + 1]) & 0x3F) << 6;
        cp |= (static_cast<uint8_t>(data[pos + 2]) & 0x3F);
        pos += 3;
        return cp;
    }
    if ((byte & 0xF8) == 0xF0 && pos + 3 < len) {
        uint32_t cp = (byte & 0x07) << 18;
        cp |= (static_cast<uint8_t>(data[pos + 1]) & 0x3F) << 12;
        cp |= (static_cast<uint8_t>(data[pos + 2]) & 0x3F) << 6;
        cp |= (static_cast<uint8_t>(data[pos + 3]) & 0x3F);
        pos += 4;
        return cp;
    }

    // Invalid byte – skip it
    pos += 1;
    return 0xFFFD;
}

/// Encode a single codepoint to UTF-8, appending to `out`.
inline void encode_utf8(uint32_t cp, std::string& out) {
    if (cp < 0x80) {
        out.push_back(static_cast<char>(cp));
    } else if (cp < 0x800) {
        out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    } else if (cp < 0x10000) {
        out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    } else {
        out.push_back(static_cast<char>(0xF0 | (cp >> 18)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    }
}

/// Decode entire UTF-8 string into a vector of codepoints.
inline std::vector<uint32_t> to_codepoints(const std::string& s) {
    std::vector<uint32_t> cps;
    cps.reserve(s.size());  // upper bound
    size_t pos = 0;
    while (pos < s.size()) {
        cps.push_back(decode_utf8(s.data(), s.size(), pos));
    }
    return cps;
}

/// Encode a vector of codepoints back to UTF-8.
inline std::string from_codepoints(const std::vector<uint32_t>& cps) {
    std::string out;
    out.reserve(cps.size() * 3);  // rough estimate for CJK-heavy text
    for (auto cp : cps) {
        encode_utf8(cp, out);
    }
    return out;
}

// Character classification helpers

inline bool is_sentence_end(uint32_t cp) {
    return cp == '.' || cp == '!' || cp == '?';
}

inline bool is_close_bracket(uint32_t cp) {
    return cp == ']' || cp == ')' || cp == '}';
}

inline bool is_open_bracket(uint32_t cp) {
    return cp == '[' || cp == '(' || cp == '{';
}

}  // anonymous namespace

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

bool is_korean(uint32_t cp) {
    return (cp >= 0xAC00 && cp <= 0xD7AF) ||  // Hangul Syllables
           (cp >= 0x1100 && cp <= 0x11FF) ||   // Hangul Jamo
           (cp >= 0x3130 && cp <= 0x318F);     // Compatibility Jamo
}

std::string fix_korean_spacing(const std::string& text) {
    if (text.empty()) {
        return text;
    }

    auto cps = to_codepoints(text);
    const size_t n = cps.size();

    // Output codepoints – worst case doubles the size
    std::vector<uint32_t> out;
    out.reserve(n + n / 4);

    for (size_t i = 0; i < n; ++i) {
        uint32_t cur = cps[i];
        uint32_t next = (i + 1 < n) ? cps[i + 1] : 0;

        // Rule 6: collapse consecutive spaces
        if (cur == ' ' && next == ' ') {
            // Skip this space; the next iteration will emit one eventually
            continue;
        }

        out.push_back(cur);

        // Nothing to do for the very last codepoint
        if (i + 1 >= n) {
            break;
        }

        // Don't insert space if next char is already a space
        if (next == ' ') {
            continue;
        }

        bool insert_space = false;

        // Rule 1: .!? + Hangul (but not ellipsis "..")
        if (is_sentence_end(cur) && is_korean(next)) {
            // Check for ellipsis: prev char is also '.'
            bool is_ellipsis = (cur == '.' && i > 0 && cps[i - 1] == '.');
            // Also check forward: next-next is '.'
            if (!is_ellipsis && cur == '.' && (i + 1 < n && cps[i + 1] == '.')) {
                is_ellipsis = true;
            }
            if (!is_ellipsis) {
                insert_space = true;
            }
        }

        // Rule 2: ])} + Hangul
        if (is_close_bracket(cur) && is_korean(next)) {
            insert_space = true;
        }

        // Rule 3: Hangul + [({
        if (is_korean(cur) && is_open_bracket(next)) {
            insert_space = true;
        }

        // Rule 4: : + Hangul
        if (cur == ':' && is_korean(next)) {
            insert_space = true;
        }

        // Rule 5: * + Hangul (markdown bold boundary)
        if (cur == '*' && is_korean(next)) {
            insert_space = true;
        }

        if (insert_space) {
            out.push_back(' ');
        }
    }

    return from_codepoints(out);
}

std::vector<std::string> fix_korean_spacing_batch(
    const std::vector<std::string>& texts) {
    std::vector<std::string> results;
    results.reserve(texts.size());
    for (const auto& t : texts) {
        results.push_back(fix_korean_spacing(t));
    }
    return results;
}

}  // namespace text_ops
}  // namespace axnmihn
