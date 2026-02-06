"""Tests for search engine functions."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def ddg_html_response():
    """Minimal DuckDuckGo HTML response with result entries."""
    return """
    <html><body>
    <div class="result">
        <a class="result__title" href="https://example.com/page1">
            <a class="result__title" href="?uddg=https%3A%2F%2Fexample.com%2Fpage1">Title One</a>
        </a>
        <a class="result__snippet">Snippet for page one</a>
    </div>
    <div class="result">
        <a class="result__title" href="https://example.com/page2">
            <a class="result__title" href="https://example.com/page2">Title Two</a>
        </a>
        <a class="result__snippet">Snippet for page two</a>
    </div>
    </body></html>
    """


class TestSearchDuckduckgo:
    """Tests for search_duckduckgo function."""

    @pytest.mark.asyncio
    async def test_parses_results(self, ddg_html_response):
        from backend.protocols.mcp.research.search_engines import search_duckduckgo

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value=ddg_html_response)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            results = await search_duckduckgo("test query", num_results=5)

        assert len(results) >= 1
        assert "title" in results[0]
        assert "url" in results[0]
        assert "snippet" in results[0]

    @pytest.mark.asyncio
    async def test_returns_empty_on_http_error(self):
        from backend.protocols.mcp.research.search_engines import search_duckduckgo

        mock_resp = AsyncMock()
        mock_resp.status = 503
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            results = await search_duckduckgo("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_timeout(self):
        from backend.protocols.mcp.research.search_engines import search_duckduckgo

        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=asyncio.TimeoutError())
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            results = await search_duckduckgo("timeout query")

        assert results == []


class TestWebSearch:
    """Tests for web_search (renamed from _google_search)."""

    @pytest.mark.asyncio
    async def test_formats_results_as_markdown(self):
        from backend.protocols.mcp.research.search_engines import web_search

        mock_results = [
            {"title": "Result 1", "url": "https://example.com/1", "snippet": "First snippet"},
            {"title": "Result 2", "url": "https://example.com/2", "snippet": "Second snippet"},
        ]

        with patch(
            "backend.protocols.mcp.research.search_engines.search_duckduckgo",
            new_callable=AsyncMock,
            return_value=mock_results,
        ):
            result = await web_search("test query", num_results=5)

        assert "## Search Results for:" in result
        assert "Result 1" in result
        assert "https://example.com/1" in result
        assert "First snippet" in result

    @pytest.mark.asyncio
    async def test_no_results_message(self):
        from backend.protocols.mcp.research.search_engines import web_search

        with patch(
            "backend.protocols.mcp.research.search_engines.search_duckduckgo",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await web_search("no results query")

        assert "No results found" in result

    def test_web_search_is_exported(self):
        """Verify web_search exists (renamed from _google_search)."""
        from backend.protocols.mcp.research.search_engines import web_search

        assert callable(web_search)


class TestTavilySearch:
    """Tests for tavily_search function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_api_key(self):
        from backend.protocols.mcp.research.search_engines import tavily_search

        with patch(
            "backend.protocols.mcp.research.search_engines.get_tavily_client",
            return_value=None,
        ):
            result = await tavily_search("test query")

        assert "검색 불가" in result or "TAVILY_API_KEY" in result

    @pytest.mark.asyncio
    async def test_formats_tavily_results(self):
        from backend.protocols.mcp.research.search_engines import tavily_search

        mock_client = MagicMock()
        mock_client.search.return_value = {
            "answer": "AI summary answer",
            "results": [
                {"title": "Source 1", "url": "https://src.com/1", "content": "Content 1"},
            ],
        }

        with patch(
            "backend.protocols.mcp.research.search_engines.get_tavily_client",
            return_value=mock_client,
        ):
            result = await tavily_search("test", max_results=5, search_depth="basic")

        assert "## Tavily Search:" in result
        assert "AI summary answer" in result
        assert "Source 1" in result

    @pytest.mark.asyncio
    async def test_handles_tavily_exception(self):
        from backend.protocols.mcp.research.search_engines import tavily_search

        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError("API error")

        with patch(
            "backend.protocols.mcp.research.search_engines.get_tavily_client",
            return_value=mock_client,
        ):
            result = await tavily_search("fail query")

        assert "오류" in result or "error" in result.lower()
