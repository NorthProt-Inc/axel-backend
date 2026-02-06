"""Research module — public API re-exports.

Provides backward-compatible imports for consumers that previously
imported from research_server.py directly.
"""

from backend.protocols.mcp.research.browser import (
    BrowserManager as BrowserManager,
    get_browser_manager as get_browser_manager,
)
from backend.protocols.mcp.research.html_processor import (
    clean_html as clean_html,
    html_to_markdown as html_to_markdown,
)
from backend.protocols.mcp.research.page_visitor import (
    deep_dive as deep_dive,
    visit_page as visit_page,
)
from backend.protocols.mcp.research.search_engines import (
    get_tavily_client as get_tavily_client,
    search_duckduckgo as search_duckduckgo,
    tavily_search as tavily_search,
    web_search as web_search,
)
