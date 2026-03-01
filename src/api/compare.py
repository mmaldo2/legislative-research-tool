"""Cross-jurisdiction bill comparison endpoints — similarity search and LLM comparison."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_llm_harness, get_session, limiter
from src.llm.harness import LLMHarness
from src.models.bill import Bill
from src.schemas.common import MetaResponse
from src.schemas.compare import (
    BillComparisonOutput,
    CompareRequest,
    SimilarBillResult,
    SimilarBillsResponse,
)
from src.search.vector import find_similar_bill_ids
from src.services.bill_service import extract_bill_text

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/bills/{bill_id}/similar", response_model=SimilarBillsResponse)
async def find_similar_bills(
    bill_id: str,
    top_k: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    min_score: float = Query(0.5, ge=0.0, le=1.0, description="Minimum cosine similarity"),
    exclude_same_jurisdiction: bool = Query(
        False, description="Exclude bills from the same jurisdiction"
    ),
    db: AsyncSession = Depends(get_session),
) -> SimilarBillsResponse:
    """Find bills similar to the given bill using pgvector cosine similarity.

    Uses bill_embeddings (Voyage-law-2, vector(1024)) for real-time cosine
    similarity search.  Falls back to the pre-computed bill_similarities table
    when no embedding exists for the source bill.
    """
    # Verify the bill exists
    result = await db.execute(select(Bill).where(Bill.id == bill_id))
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    matches = await find_similar_bill_ids(
        db,
        bill_id,
        exclude_jurisdiction=bill.jurisdiction_id if exclude_same_jurisdiction else None,
        min_score=min_score,
        top_k=top_k,
    )
    if not matches:
        return SimilarBillsResponse(
            data=[],
            meta=MetaResponse(total_count=0, ai_enriched=False),
        )

    # Load full bill metadata for each matched bill
    matched_ids = [m.bill_id for m in matches]
    score_map = {m.bill_id: m.score for m in matches}

    bills_result = await db.execute(select(Bill).where(Bill.id.in_(matched_ids)))
    bills_by_id = {b.id: b for b in bills_result.scalars().all()}

    data: list[SimilarBillResult] = []
    for matched_id in matched_ids:
        matched_bill = bills_by_id.get(matched_id)
        if not matched_bill:
            continue
        data.append(
            SimilarBillResult(
                bill_id=matched_bill.id,
                identifier=matched_bill.identifier,
                title=matched_bill.title,
                jurisdiction_id=matched_bill.jurisdiction_id,
                status=matched_bill.status,
                similarity_score=score_map[matched_id],
            )
        )

    # Sort by descending similarity
    data.sort(key=lambda r: r.similarity_score, reverse=True)

    return SimilarBillsResponse(
        data=data,
        meta=MetaResponse(total_count=len(data), ai_enriched=False),
    )


@router.post("/analyze/compare", response_model=BillComparisonOutput)
@limiter.limit("10/minute")
async def compare_bills(
    request: Request,
    req: CompareRequest,
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
) -> BillComparisonOutput:
    """Generate an LLM comparison of two bills. Cached by content hash."""
    # Load bill A
    stmt_a = select(Bill).where(Bill.id == req.bill_id_a).options(selectinload(Bill.texts))
    result_a = await db.execute(stmt_a)
    bill_a = result_a.scalar_one_or_none()
    if not bill_a:
        raise HTTPException(status_code=404, detail=f"Bill not found: {req.bill_id_a}")

    # Load bill B
    stmt_b = select(Bill).where(Bill.id == req.bill_id_b).options(selectinload(Bill.texts))
    result_b = await db.execute(stmt_b)
    bill_b = result_b.scalar_one_or_none()
    if not bill_b:
        raise HTTPException(status_code=404, detail=f"Bill not found: {req.bill_id_b}")

    # Extract text for each bill (latest version, fall back to title)
    bill_a_text = extract_bill_text(bill_a)
    bill_b_text = extract_bill_text(bill_b)

    output = await harness.compare(
        bill_id_a=bill_a.id,
        bill_id_b=bill_b.id,
        bill_a_text=bill_a_text,
        bill_a_identifier=bill_a.identifier,
        bill_a_title=bill_a.title,
        bill_b_text=bill_b_text,
        bill_b_identifier=bill_b.identifier,
        bill_b_title=bill_b.title,
    )
    await db.commit()
    return output
