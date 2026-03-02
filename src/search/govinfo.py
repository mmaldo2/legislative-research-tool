"""GovInfo API client for searching and retrieving federal government documents.

Provides access to the GovInfo API (api.govinfo.gov) for searching across
federal publications including bills, hearings, reports, and regulations.
Used as a live query tool by the research assistant chat.
"""

import logging
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0


async def search_govinfo(
    query: str,
    collection: str | None = None,
    page_size: int = 10,
    offset: int = 0,
    congress: str | None = None,
    doc_class: str | None = None,
    date_range: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Search the GovInfo API for federal government documents.

    Args:
        query: Search terms.
        collection: GovInfo collection code (e.g. BILLS, CRPT, CHRG, FR).
        page_size: Results per page (max 100).
        doc_class: Document class filter (e.g. hr, s, hjres).
        congress: Congress number filter (e.g. "118").
        date_range: Optional {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}.

    Returns:
        Dict with results list and pagination metadata.
    """
    if not settings.govinfo_api_key:
        return {"error": "GovInfo API key not configured.", "results": []}

    url = f"{settings.govinfo_api_url}/search"
    params: dict[str, Any] = {
        "api_key": settings.govinfo_api_key,
    }

    # Build search body per GovInfo API specification
    body: dict[str, Any] = {
        "query": query,
        "pageSize": min(page_size, 100),
        "offsetMark": "*" if offset == 0 else str(offset),
    }

    # Apply filters
    if collection:
        body["collection"] = collection
    if congress:
        body["congress"] = congress
    if doc_class:
        body["docClass"] = doc_class
    if date_range:
        body["publishDateFrom"] = date_range.get("start", "")
        body["publishDateTo"] = date_range.get("end", "")

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, params=params, json=body)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("GovInfo API HTTP error: %s", exc.response.status_code)
        return {
            "error": f"GovInfo API returned {exc.response.status_code}.",
            "results": [],
        }
    except httpx.RequestError as exc:
        logger.warning("GovInfo API request error: %s", exc)
        return {"error": "GovInfo API is unavailable.", "results": []}

    # Normalize response
    results = []
    for pkg in data.get("results", []):
        results.append(
            {
                "package_id": pkg.get("packageId", ""),
                "title": pkg.get("title", ""),
                "collection_code": pkg.get("collectionCode", ""),
                "date_issued": pkg.get("dateIssued", ""),
                "congress": pkg.get("congress", ""),
                "doc_class": pkg.get("docClass", ""),
                "government_author": pkg.get("governmentAuthor1", ""),
                "category": pkg.get("category", ""),
                "download_url": pkg.get("download", {}).get("txtLink", ""),
            }
        )

    return {
        "results": results,
        "count": data.get("count", len(results)),
        "offset": data.get("nextOffset", ""),
    }


async def get_govinfo_package(package_id: str) -> dict[str, Any]:
    """Retrieve metadata for a specific GovInfo package.

    Args:
        package_id: GovInfo package identifier (e.g. BILLS-118hr1234ih).

    Returns:
        Dict with package metadata including download links.
    """
    if not settings.govinfo_api_key:
        return {"error": "GovInfo API key not configured."}

    url = f"{settings.govinfo_api_url}/packages/{package_id}/summary"
    params = {"api_key": settings.govinfo_api_key}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("GovInfo package fetch error: %s", exc.response.status_code)
        return {"error": f"Package '{package_id}' not found or API error."}
    except httpx.RequestError as exc:
        logger.warning("GovInfo request error: %s", exc)
        return {"error": "GovInfo API is unavailable."}

    return {
        "package_id": data.get("packageId", package_id),
        "title": data.get("title", ""),
        "collection_code": data.get("collectionCode", ""),
        "collection_name": data.get("collectionName", ""),
        "category": data.get("category", ""),
        "date_issued": data.get("dateIssued", ""),
        "congress": data.get("congress", ""),
        "session": data.get("session", ""),
        "doc_class": data.get("docClass", ""),
        "pages": data.get("pages", ""),
        "government_author": data.get("governmentAuthor1", ""),
        "suDoc_class_number": data.get("suDocClassNumber", ""),
        "download": {
            "pdf": data.get("download", {}).get("pdfLink", ""),
            "text": data.get("download", {}).get("txtLink", ""),
            "xml": data.get("download", {}).get("xmlLink", ""),
        },
        "related_link": data.get("relatedLink", ""),
        "detail_link": data.get("detailLink", ""),
    }
