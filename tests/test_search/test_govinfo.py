"""Tests for the GovInfo API client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.search.govinfo import get_govinfo_package, search_govinfo


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    """Ensure govinfo_api_key is set for tests."""
    monkeypatch.setattr("src.search.govinfo.settings.govinfo_api_key", "test-key")
    monkeypatch.setattr(
        "src.search.govinfo.settings.govinfo_api_url",
        "https://api.govinfo.gov",
    )


class TestSearchGovinfo:
    @pytest.mark.asyncio
    async def test_returns_normalized_results(self):
        mock_response = {
            "count": 2,
            "results": [
                {
                    "packageId": "BILLS-118hr1234ih",
                    "title": "Test Bill Act",
                    "collectionCode": "BILLS",
                    "dateIssued": "2024-01-15",
                    "congress": "118",
                    "docClass": "hr",
                    "governmentAuthor1": "House",
                    "category": "Bills and Statutes",
                    "download": {"txtLink": "https://example.com/text.txt"},
                },
                {
                    "packageId": "CRPT-118srpt25",
                    "title": "Committee Report on Test Bill",
                    "collectionCode": "CRPT",
                    "dateIssued": "2024-02-10",
                    "congress": "118",
                    "docClass": "srpt",
                    "governmentAuthor1": "Senate",
                    "category": "Congressional Reports",
                    "download": {},
                },
            ],
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()

        with patch("src.search.govinfo.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            result = await search_govinfo("test bill", collection="BILLS")

        assert result["count"] == 2
        assert len(result["results"]) == 2
        assert result["results"][0]["package_id"] == "BILLS-118hr1234ih"
        assert result["results"][0]["title"] == "Test Bill Act"
        assert result["results"][0]["collection_code"] == "BILLS"
        assert result["results"][1]["download_url"] == ""

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_error(self, monkeypatch):
        monkeypatch.setattr("src.search.govinfo.settings.govinfo_api_key", "")
        result = await search_govinfo("test")
        assert "error" in result
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_http_error_returns_error(self):
        with patch("src.search.govinfo.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=httpx.Request("POST", "https://example.com"),
                response=httpx.Response(404),
            )
            mock_client_cls.return_value = mock_client

            result = await search_govinfo("test")

        assert "error" in result
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_request_error_returns_error(self):
        with patch("src.search.govinfo.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.side_effect = httpx.RequestError("timeout")
            mock_client_cls.return_value = mock_client

            result = await search_govinfo("test")

        assert "error" in result
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_applies_filters_to_request_body(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"count": 0, "results": []}
        mock_resp.raise_for_status = MagicMock()

        with patch("src.search.govinfo.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            await search_govinfo("climate", collection="FR", congress="118", page_size=25)

            call_args = mock_client.post.call_args
            body = call_args.kwargs.get("json", call_args[1].get("json", {}))
            assert body["query"] == "climate"
            assert body["collection"] == "FR"
            assert body["congress"] == "118"
            assert body["pageSize"] == 25


class TestGetGovinfoPackage:
    @pytest.mark.asyncio
    async def test_returns_package_metadata(self):
        mock_data = {
            "packageId": "BILLS-118hr1234ih",
            "title": "Test Bill Act",
            "collectionCode": "BILLS",
            "collectionName": "Congressional Bills",
            "category": "Bills and Statutes",
            "dateIssued": "2024-01-15",
            "congress": "118",
            "session": "2",
            "docClass": "hr",
            "pages": "12",
            "governmentAuthor1": "House",
            "suDocClassNumber": "Y 1.1/3:",
            "download": {
                "pdfLink": "https://example.com/doc.pdf",
                "txtLink": "https://example.com/doc.txt",
                "xmlLink": "https://example.com/doc.xml",
            },
            "relatedLink": "https://example.com/related",
            "detailLink": "https://example.com/detail",
        }

        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_data
        mock_resp.raise_for_status = MagicMock()

        with patch("src.search.govinfo.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            result = await get_govinfo_package("BILLS-118hr1234ih")

        assert result["package_id"] == "BILLS-118hr1234ih"
        assert result["title"] == "Test Bill Act"
        assert result["congress"] == "118"
        assert result["download"]["pdf"] == "https://example.com/doc.pdf"
        assert result["download"]["text"] == "https://example.com/doc.txt"

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_error(self, monkeypatch):
        monkeypatch.setattr("src.search.govinfo.settings.govinfo_api_key", "")
        result = await get_govinfo_package("BILLS-118hr1234ih")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_package_not_found_returns_error(self):
        with patch("src.search.govinfo.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(404),
            )
            mock_client_cls.return_value = mock_client

            result = await get_govinfo_package("NONEXISTENT")

        assert "error" in result


class TestToolHandlers:
    """Test the GovInfo tool handler functions in chat.py."""

    @pytest.mark.asyncio
    async def test_search_govinfo_handler_calls_client(self):
        with patch("src.api.chat.search_govinfo", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"results": [], "count": 0}

            from src.api.chat import _tool_search_govinfo

            result_str = await _tool_search_govinfo(
                {"query": "test", "collection": "BILLS"},
                db=AsyncMock(),
                harness=AsyncMock(),
            )
            result = json.loads(result_str)
            assert result["count"] == 0
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_govinfo_document_handler_calls_client(self):
        with patch("src.api.chat.get_govinfo_package", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "package_id": "BILLS-118hr1234ih",
                "title": "Test",
            }

            from src.api.chat import _tool_get_govinfo_document

            result_str = await _tool_get_govinfo_document(
                {"package_id": "BILLS-118hr1234ih"},
                db=AsyncMock(),
                harness=AsyncMock(),
            )
            result = json.loads(result_str)
            assert result["package_id"] == "BILLS-118hr1234ih"
            mock_get.assert_called_once_with("BILLS-118hr1234ih")
