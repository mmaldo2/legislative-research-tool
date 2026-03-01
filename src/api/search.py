"""Hybrid search endpoint."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.bill import Bill
from src.schemas.common import MetaResponse
from src.schemas.search import SearchResponse, SearchResult
from src.search.engine import hybrid_search

router = APIRouter()

# Upper bound on search results — keeps memory bounded while allowing accurate totals
_MAX_SEARCH_RESULTS = 1000


@router.get("/search/bills", response_model=SearchResponse)
async def search_bills(
    q: str = Query(..., description="Search query"),
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    mode: str = Query("hybrid", description="Search mode: keyword, semantic, or hybrid"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> SearchResponse:
    """Search bills using hybrid keyword + semantic search with RRF fusion."""
    # Fetch all ranked results up to ceiling for accurate total_count
    results = await hybrid_search(
        session=db,
        query=q,
        mode=mode,
        jurisdiction=jurisdiction,
        top_k=_MAX_SEARCH_RESULTS,
    )

    total = len(results)

    # Paginate from full result set
    start = (page - 1) * per_page
    page_results = results[start : start + per_page]

    if not page_results:
        return SearchResponse(
            data=[],
            meta=MetaResponse(total_count=total, page=page, per_page=per_page),
        )

    # Fetch bill details for the page
    bill_ids = [r[0] for r in page_results]

    stmt = select(Bill).where(Bill.id.in_(bill_ids))
    result = await db.execute(stmt)
    bills_by_id = {b.id: b for b in result.scalars().all()}

    data = []
    for bill_id, score in page_results:
        bill = bills_by_id.get(bill_id)
        if not bill:
            continue
        snippet = bill.title[:200] if bill.title else None
        data.append(
            SearchResult(
                bill_id=bill.id,
                identifier=bill.identifier,
                title=bill.title,
                jurisdiction_id=bill.jurisdiction_id,
                status=bill.status,
                score=score,
                snippet=snippet,
            )
        )

    return SearchResponse(
        data=data,
        meta=MetaResponse(
            total_count=total,
            page=page,
            per_page=per_page,
            sources=["bm25", "voyage-law-2"] if mode == "hybrid" else [mode],
        ),
    )
