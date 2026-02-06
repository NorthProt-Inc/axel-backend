"""Page visiting and deep-dive research functions."""

import asyncio
import re
import time
from urllib.parse import urlparse

from backend.core.logging import get_logger
from backend.core.research_artifacts import (
    ARTIFACT_THRESHOLD,
    process_content_for_artifact,
)
from backend.protocols.mcp.research.browser import get_browser_manager
from backend.protocols.mcp.research.config import (
    NAVIGATION_TIMEOUT_MS,
    PAGE_TIMEOUT_MS,
    SELECTOR_TIMEOUT_MS,
)
from backend.protocols.mcp.research.html_processor import html_to_markdown
from backend.protocols.mcp.research.search_engines import search_duckduckgo

_log = get_logger("research.page_visitor")


async def visit_page(url: str) -> str:
    """Visit a URL with headless browser and return markdown content.

    Args:
        url: Full URL to visit (http/https only)

    Returns:
        Markdown content or error message
    """
    start_time = time.time()
    _log.info("Page visit starting", url=url[:100])

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"Error: Invalid URL scheme. Only http/https supported: {url}"

    page = None
    try:
        manager = await get_browser_manager()
        page = await manager.get_page()

        page.set_default_timeout(PAGE_TIMEOUT_MS)
        page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)

        response = await page.goto(url, wait_until="networkidle")

        if response is None or response.status >= 400:
            status = response.status if response else "unknown"
            return f"Error: Failed to load page. Status: {status}"

        await page.wait_for_load_state("networkidle")

        try:
            await page.wait_for_selector(
                "article, main, .content, #content, .post, .entry",
                timeout=SELECTOR_TIMEOUT_MS,
            )
        except (asyncio.TimeoutError, Exception):
            pass

        html = await page.content()
        title = await page.title()

        markdown = html_to_markdown(html, url)

        output = f"# {title}\n\n"
        output += f"**Source:** {url}\n\n"
        output += "---\n\n"
        output += markdown

        dur_ms = int((time.time() - start_time) * 1000)
        _log.info("Page visit complete", url=url[:80], dur_ms=dur_ms, content_len=len(output))
        return process_content_for_artifact(url, output)

    except asyncio.TimeoutError:
        dur_ms = int((time.time() - start_time) * 1000)
        _log.warning("Page visit timeout, extracting partial content", url=url[:80], dur_ms=dur_ms)
        try:
            html = await page.content()
            title = await page.title()
            markdown = html_to_markdown(html, url)
            if markdown and len(markdown.strip()) > 100:
                output = f"# {title}\n\n"
                output += f"**Source:** {url}\n\n"
                output += f"**Note:** Page timed out after {dur_ms / 1000:.1f}s, partial content returned.\n\n"
                output += "---\n\n"
                output += markdown
                _log.info(
                    "Page visit timeout but partial content extracted",
                    url=url[:80],
                    content_len=len(output),
                )
                return process_content_for_artifact(url, output)
        except Exception as e:
            _log.debug("Partial content extraction failed", url=url[:50], error=str(e))
        return f"Error: Page load timed out after {NAVIGATION_TIMEOUT_MS / 1000}s (no usable content): {url}"
    except Exception as e:
        dur_ms = int((time.time() - start_time) * 1000)
        _log.error("Page visit error", url=url[:80], dur_ms=dur_ms, error=str(e))
        return f"Error visiting page: {str(e)}"
    finally:
        if page:
            try:
                await page.close()
            except Exception as e:
                _log.warning("Page close failed, potential leak", url=url[:50], error=str(e))


async def deep_dive(query: str) -> str:
    """Comprehensive research: search + visit top pages + compile findings.

    Args:
        query: Research query string

    Returns:
        Structured research report in markdown
    """
    start_time = time.time()
    _log.info("Deep dive starting", query=query[:80])

    output = f"# Deep Dive Research: {query}\n\n"
    output += "## Phase 1: Search Results\n\n"

    results = await search_duckduckgo(query, num_results=5)

    if not results:
        return f"Deep dive failed: No search results for '{query}'"

    for i, r in enumerate(results, 1):
        output += f"{i}. **{r['title']}**\n   {r['url']}\n\n"

    output += "---\n\n## Phase 2: Content Extraction\n\n"

    visited_content: list[dict] = []
    urls_to_visit = [r["url"] for r in results[:3]]

    tasks = [visit_page(url) for url in urls_to_visit]
    page_contents = await asyncio.gather(*tasks, return_exceptions=True)

    artifact_paths: list[str] = []

    for i, (url, content) in enumerate(zip(urls_to_visit, page_contents), 1):
        output += f"### Source {i}: {url}\n\n"

        if isinstance(content, Exception):
            output += f"*Failed to retrieve: {str(content)}*\n\n"
        else:
            is_artifact = content.strip().startswith("[ARTIFACT SAVED]")

            if is_artifact:
                visited_content.append({"url": url, "content": content, "is_artifact": True})
                output += f"{content}\n\n"

                path_match = re.search(r"Path: ([^\n]+)", content)
                if path_match:
                    artifact_paths.append(path_match.group(1))
            else:
                content_lines = content.split("\n")
                content_body = "\n".join(content_lines[4:])[:4000]

                if content_body.strip():
                    visited_content.append({"url": url, "content": content_body, "is_artifact": False})
                    output += f"{content_body}\n\n"
                else:
                    output += "*No meaningful content extracted*\n\n"

        output += "---\n\n"

    output += "## Phase 3: Research Summary\n\n"
    output += f"**Query:** {query}\n"
    output += f"**Sources Analyzed:** {len(visited_content)}/{len(urls_to_visit)}\n"

    total_chars = sum(
        len(c["content"]) if not c.get("is_artifact") else ARTIFACT_THRESHOLD
        for c in visited_content
    )
    output += f"**Total Content Length:** {total_chars:,} characters\n\n"

    if visited_content:
        output += "**Key Sources:**\n"
        for vc in visited_content:
            artifact_marker = " (artifact)" if vc.get("is_artifact") else ""
            output += f"- {vc['url']}{artifact_marker}\n"

    if artifact_paths:
        output += "\n**Saved Artifacts:**\n"
        for path in artifact_paths:
            output += f"- `{path}`\n"
        output += "\n_Use `read_artifact` tool to retrieve full content from saved artifacts._\n"

    dur_ms = int((time.time() - start_time) * 1000)
    _log.info(
        "Deep dive complete",
        query=query[:50],
        dur_ms=dur_ms,
        sources=len(visited_content),
        artifacts=len(artifact_paths),
    )
    return output
