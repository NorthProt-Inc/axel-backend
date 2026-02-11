"""HTML cleaning and markdown conversion for research pages."""

import re
from urllib.parse import urljoin

from markdownify import MarkdownConverter

from backend.protocols.mcp.research.config import (
    AD_PATTERNS,
    EXCLUDED_TAGS,
    MAX_CONTENT_LENGTH,
)

# Pre-compiled regex patterns (avoids 33+ re.compile() calls per invocation)
_AD_PATTERN_RE = re.compile("|".join(AD_PATTERNS), re.I)
_DISPLAY_NONE_RE = re.compile(r"display:\s*none", re.I)
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r" {2,}")


class _Converter(MarkdownConverter):
    """Markdown converter with link resolution and image stripping.

    Defined at module scope to avoid class-creation overhead per call.
    ``base_url`` is passed via the *options* dict that MarkdownConverter
    already propagates to every ``convert_*`` method.
    """

    def convert_a(self, el, text, **kwargs):
        href = el.get("href", "")
        base_url = self.options.get("base_url", "")
        if href and not href.startswith(("http://", "https://", "mailto:", "#")):
            href = urljoin(base_url, href)
        if not text.strip():
            return ""
        return f"[{text}]({href})" if href else text

    def convert_img(self, el, text, **kwargs):
        return ""


def clean_html(html: str) -> str:
    """Remove noise elements from HTML for content extraction.

    Strips scripts, styles, ads, hidden elements, and comments.
    Uses at most 3 DOM traversals (excluded tags, ad patterns, hidden
    elements) instead of the previous 47.

    Args:
        html: Raw HTML string

    Returns:
        Cleaned HTML string
    """
    if not html:
        return ""

    from bs4 import BeautifulSoup, Comment

    soup = BeautifulSoup(html, "html.parser")

    # Traversal 1: remove comments and excluded tags in one pass
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    for tag in EXCLUDED_TAGS:
        for element in soup.find_all(tag):
            element.decompose()

    # Traversal 2: remove ad elements by class (single combined regex)
    for element in soup.find_all(class_=_AD_PATTERN_RE):
        element.decompose()

    # Traversal 3: remove ad elements by id (single combined regex)
    for element in soup.find_all(id=_AD_PATTERN_RE):
        element.decompose()

    # Traversal 4 (bonus): remove display:none elements
    for element in soup.find_all(style=_DISPLAY_NONE_RE):
        element.decompose()

    return str(soup)


def html_to_markdown(html: str, base_url: str = "") -> str:
    """Convert HTML to clean markdown with content limits.

    Args:
        html: Raw HTML string
        base_url: Base URL for resolving relative links

    Returns:
        Markdown string, truncated if exceeding MAX_CONTENT_LENGTH
    """
    if not html:
        return ""

    cleaned_html = clean_html(html)

    markdown = _Converter(
        heading_style="ATX",
        bullets="-",
        strip=["script", "style", "noscript", "iframe"],
        base_url=base_url,  # type: ignore[call-arg]
    ).convert(cleaned_html)

    markdown = _MULTI_NEWLINE_RE.sub("\n\n", markdown)
    markdown = _MULTI_SPACE_RE.sub(" ", markdown)
    markdown = markdown.strip()

    if len(markdown) > MAX_CONTENT_LENGTH:
        markdown = markdown[:MAX_CONTENT_LENGTH] + "\n\n[Content truncated due to length...]"

    return markdown
