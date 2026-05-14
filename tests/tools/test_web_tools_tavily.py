"""Tests for Tavily web backend integration.

Coverage:
  _tavily_request() — API key handling, endpoint construction, error propagation.
  _normalize_tavily_search_results() — search response normalization.
  _normalize_tavily_documents() — extract/crawl response normalization, failed_results.
  web_search_tool / web_extract_tool / web_crawl_tool — Tavily dispatch paths.
  Async behaviour — non-blocking, client reuse.
"""

import json
import os
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_async_client_mock(json_return: dict) -> MagicMock:
    """Return a mock httpx.AsyncClient whose .post() is an AsyncMock."""
    mock_response = MagicMock()
    mock_response.json.return_value = json_return
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


# ─── _tavily_request ─────────────────────────────────────────────────────────

class TestTavilyRequest:
    """Test suite for the _tavily_request helper."""

    def test_raises_without_api_key(self):
        """No TAVILY_API_KEY → ValueError with guidance."""
        import tools.web_tools as wt
        wt._TAVILY_CLIENT = None
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TAVILY_API_KEY", None)
            with pytest.raises(ValueError, match="TAVILY_API_KEY"):
                asyncio.run(wt._tavily_request("search", {"query": "test"}))

    def test_posts_with_api_key_in_body(self):
        """api_key is injected into the JSON payload."""
        import tools.web_tools as wt

        mock_client = _make_async_client_mock({"results": []})

        with patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test-key"}), \
             patch("tools.web_tools._get_tavily_client", return_value=mock_client):
            asyncio.run(wt._tavily_request("search", {"query": "hello"}))

            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert payload["api_key"] == "tvly-test-key"
            assert payload["query"] == "hello"
            first_arg = call_kwargs.args[0] if call_kwargs.args else ""
            assert "api.tavily.com/search" in first_arg

    def test_raises_on_http_error(self):
        """Non-2xx responses propagate as httpx.HTTPStatusError."""
        import httpx as _httpx
        import tools.web_tools as wt

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = _httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-bad-key"}), \
             patch("tools.web_tools._get_tavily_client", return_value=mock_client):
            with pytest.raises(_httpx.HTTPStatusError):
                asyncio.run(wt._tavily_request("search", {"query": "test"}))


# ─── Async non-blocking test ──────────────────────────────────────────────────

class TestTavilyRequestAsync:
    """Verify that _tavily_request is genuinely non-blocking."""

    def test_tavily_request_async_no_event_loop_block(self):
        """A sentinel scheduled via asyncio.sleep(0.01) must fire within 50ms
        of _tavily_request starting, even when the mock HTTP call sleeps 0.3s.
        """
        import tools.web_tools as wt
        import time

        sentinel_fired_at: list = []

        async def slow_post(*args, **kwargs):
            await asyncio.sleep(0.3)
            mock_response = MagicMock()
            mock_response.json.return_value = {"results": []}
            mock_response.raise_for_status = MagicMock()
            return mock_response

        mock_client = MagicMock()
        mock_client.post = slow_post

        async def run():
            start = time.monotonic()

            async def sentinel():
                await asyncio.sleep(0.01)
                sentinel_fired_at.append(time.monotonic() - start)

            with patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}), \
                 patch("tools.web_tools._get_tavily_client", return_value=mock_client):
                await asyncio.gather(
                    wt._tavily_request("search", {"query": "x"}),
                    sentinel(),
                )

        asyncio.run(run())
        assert sentinel_fired_at, "Sentinel never fired"
        # Sentinel should fire well before the 0.3s mock HTTP delay completes.
        assert sentinel_fired_at[0] < 0.05, (
            f"Sentinel fired at {sentinel_fired_at[0]:.3f}s — event loop was blocked"
        )

    def test_tavily_client_reused(self):
        """Calling _tavily_request twice must not instantiate a second AsyncClient."""
        import tools.web_tools as wt

        # Pre-seed the module-level client with our mock.
        mock_client = _make_async_client_mock({"results": []})
        wt._TAVILY_CLIENT = mock_client

        get_client_call_count = 0
        original_get = wt._get_tavily_client

        def counting_get():
            nonlocal get_client_call_count
            get_client_call_count += 1
            return original_get()

        async def run():
            with patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}), \
                 patch("tools.web_tools._get_tavily_client", side_effect=counting_get):
                await wt._tavily_request("search", {"query": "first"})
                await wt._tavily_request("search", {"query": "second"})

        asyncio.run(run())

        # _get_tavily_client called once per request — but always returns the
        # same pre-seeded mock (i.e., only one AsyncClient was ever constructed).
        assert get_client_call_count == 2
        assert mock_client.post.call_count == 2


# ─── _normalize_tavily_search_results ─────────────────────────────────────────

class TestNormalizeTavilySearchResults:
    """Test search result normalization."""

    def test_basic_normalization(self):
        from tools.web_tools import _normalize_tavily_search_results
        raw = {
            "results": [
                {"title": "Python Docs", "url": "https://docs.python.org", "content": "Official docs", "score": 0.9},
                {"title": "Tutorial", "url": "https://example.com", "content": "A tutorial", "score": 0.8},
            ]
        }
        result = _normalize_tavily_search_results(raw)
        assert result["success"] is True
        web = result["data"]["web"]
        assert len(web) == 2
        assert web[0]["title"] == "Python Docs"
        assert web[0]["url"] == "https://docs.python.org"
        assert web[0]["description"] == "Official docs"
        assert web[0]["position"] == 1
        assert web[1]["position"] == 2

    def test_empty_results(self):
        from tools.web_tools import _normalize_tavily_search_results
        result = _normalize_tavily_search_results({"results": []})
        assert result["success"] is True
        assert result["data"]["web"] == []

    def test_missing_fields(self):
        from tools.web_tools import _normalize_tavily_search_results
        result = _normalize_tavily_search_results({"results": [{}]})
        web = result["data"]["web"]
        assert web[0]["title"] == ""
        assert web[0]["url"] == ""
        assert web[0]["description"] == ""


# ─── _normalize_tavily_documents ──────────────────────────────────────────────

class TestNormalizeTavilyDocuments:
    """Test extract/crawl document normalization."""

    def test_basic_document(self):
        from tools.web_tools import _normalize_tavily_documents
        raw = {
            "results": [{
                "url": "https://example.com",
                "title": "Example",
                "raw_content": "Full page content here",
            }]
        }
        docs = _normalize_tavily_documents(raw)
        assert len(docs) == 1
        assert docs[0]["url"] == "https://example.com"
        assert docs[0]["title"] == "Example"
        assert docs[0]["content"] == "Full page content here"
        assert docs[0]["raw_content"] == "Full page content here"
        assert docs[0]["metadata"]["sourceURL"] == "https://example.com"

    def test_falls_back_to_content_when_no_raw_content(self):
        from tools.web_tools import _normalize_tavily_documents
        raw = {"results": [{"url": "https://example.com", "content": "Snippet"}]}
        docs = _normalize_tavily_documents(raw)
        assert docs[0]["content"] == "Snippet"

    def test_failed_results_included(self):
        from tools.web_tools import _normalize_tavily_documents
        raw = {
            "results": [],
            "failed_results": [
                {"url": "https://fail.com", "error": "timeout"},
            ],
        }
        docs = _normalize_tavily_documents(raw)
        assert len(docs) == 1
        assert docs[0]["url"] == "https://fail.com"
        assert docs[0]["error"] == "timeout"
        assert docs[0]["content"] == ""

    def test_failed_urls_included(self):
        from tools.web_tools import _normalize_tavily_documents
        raw = {
            "results": [],
            "failed_urls": ["https://bad.com"],
        }
        docs = _normalize_tavily_documents(raw)
        assert len(docs) == 1
        assert docs[0]["url"] == "https://bad.com"
        assert docs[0]["error"] == "extraction failed"

    def test_fallback_url(self):
        from tools.web_tools import _normalize_tavily_documents
        raw = {"results": [{"content": "data"}]}
        docs = _normalize_tavily_documents(raw, fallback_url="https://fallback.com")
        assert docs[0]["url"] == "https://fallback.com"


# ─── web_search_tool (Tavily dispatch) ────────────────────────────────────────

class TestWebSearchTavily:
    """Test web_search_tool dispatch to Tavily."""

    def test_search_dispatches_to_tavily(self):
        mock_client = _make_async_client_mock({
            "results": [{"title": "Result", "url": "https://r.com", "content": "desc", "score": 0.9}]
        })

        with patch("tools.web_tools._get_backend", return_value="tavily"), \
             patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}), \
             patch("tools.web_tools._get_tavily_client", return_value=mock_client), \
             patch("tools.interrupt.is_interrupted", return_value=False):
            from tools.web_tools import web_search_tool
            result = json.loads(web_search_tool("test query", limit=3))
            assert result["success"] is True
            assert len(result["data"]["web"]) == 1
            assert result["data"]["web"][0]["title"] == "Result"


# ─── web_extract_tool (Tavily dispatch) ───────────────────────────────────────

class TestWebExtractTavily:
    """Test web_extract_tool dispatch to Tavily."""

    def test_extract_dispatches_to_tavily(self):
        mock_client = _make_async_client_mock({
            "results": [{"url": "https://example.com", "raw_content": "Extracted content", "title": "Page"}]
        })

        with patch("tools.web_tools._get_backend", return_value="tavily"), \
             patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}), \
             patch("tools.web_tools._get_tavily_client", return_value=mock_client), \
             patch("tools.web_tools.process_content_with_llm", return_value=None):
            from tools.web_tools import web_extract_tool
            result = json.loads(asyncio.run(
                web_extract_tool(["https://example.com"], use_llm_processing=False)
            ))
            assert "results" in result
            assert len(result["results"]) == 1
            assert result["results"][0]["url"] == "https://example.com"


# ─── web_crawl_tool (Tavily dispatch) ─────────────────────────────────────────

class TestWebCrawlTavily:
    """Test web_crawl_tool dispatch to Tavily."""

    def test_crawl_dispatches_to_tavily(self):
        mock_client = _make_async_client_mock({
            "results": [
                {"url": "https://example.com/page1", "raw_content": "Page 1 content", "title": "Page 1"},
                {"url": "https://example.com/page2", "raw_content": "Page 2 content", "title": "Page 2"},
            ]
        })

        with patch("tools.web_tools._get_backend", return_value="tavily"), \
             patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}), \
             patch("tools.web_tools._get_tavily_client", return_value=mock_client), \
             patch("tools.web_tools.check_website_access", return_value=None), \
             patch("tools.web_tools.is_safe_url", return_value=True), \
             patch("tools.interrupt.is_interrupted", return_value=False):
            from tools.web_tools import web_crawl_tool
            result = json.loads(asyncio.run(
                web_crawl_tool("https://example.com", use_llm_processing=False)
            ))
            assert "results" in result
            assert len(result["results"]) == 2
            assert result["results"][0]["title"] == "Page 1"

    def test_crawl_sends_instructions(self):
        """Instructions are included in the Tavily crawl payload."""
        mock_client = _make_async_client_mock({"results": []})

        with patch("tools.web_tools._get_backend", return_value="tavily"), \
             patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}), \
             patch("tools.web_tools._get_tavily_client", return_value=mock_client), \
             patch("tools.web_tools.check_website_access", return_value=None), \
             patch("tools.web_tools.is_safe_url", return_value=True), \
             patch("tools.interrupt.is_interrupted", return_value=False):
            from tools.web_tools import web_crawl_tool
            asyncio.run(
                web_crawl_tool("https://example.com", instructions="Find docs", use_llm_processing=False)
            )
            call_kwargs = mock_client.post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert payload["instructions"] == "Find docs"
            assert payload["url"] == "https://example.com"
