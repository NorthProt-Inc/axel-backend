"""Research module configuration constants.

Centralizes magic numbers and configuration values used across
the research subsystem (browser management, HTML processing, search).
"""

from backend.config import (
    RESEARCH_PAGE_TIMEOUT_MS,
    RESEARCH_NAVIGATION_TIMEOUT_MS,
    RESEARCH_MAX_CONTENT_LENGTH,
)

# Browser management
BROWSER_MAX_USES: int = 50
BROWSER_IDLE_TIMEOUT: int = 300  # seconds (5 min)
SELECTOR_TIMEOUT_MS: int = 5000

# Page loading
PAGE_TIMEOUT_MS: int = RESEARCH_PAGE_TIMEOUT_MS
NAVIGATION_TIMEOUT_MS: int = RESEARCH_NAVIGATION_TIMEOUT_MS

# Content limits
MAX_CONTENT_LENGTH: int = RESEARCH_MAX_CONTENT_LENGTH

# HTML cleaning
EXCLUDED_TAGS: list[str] = [
    "script", "style", "noscript", "iframe", "svg", "path", "meta", "link",
    "header", "footer", "nav", "aside", "advertisement", "ads", "ad-container",
    "cookie-banner", "cookie-consent", "popup", "modal", "sidebar",
]

AD_PATTERNS: list[str] = [
    "ad", "ads", "advert", "advertisement", "banner", "popup", "modal",
    "cookie", "consent", "newsletter", "subscribe", "sidebar", "related",
    "recommended", "sponsored", "promo", "social-share", "share-buttons",
]

# User agents for browser rotation
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]
