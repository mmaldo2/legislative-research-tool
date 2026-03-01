"""Cross-jurisdiction bill comparison endpoints — similarity search and LLM comparison."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, text
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

    # Try pgvector cosine similarity first
    embedding_query = text("""
        SELECT be2.bill_id,
               1 - (be1.embedding <=> be2.embedding) AS score
        FROM bill_embeddings be1
        JOIN bill_embeddings be2 ON be1.bill_id != be2.bill_id
        JOIN bills b ON b.id = be2.bill_id
        WHERE be1.bill_id = :bill_id
          AND 1 - (be1.embedding <=> be2.embedding) > :min_score
        ORDER BY be1.embedding <=> be2.embedding
        LIMIT :top_k
    """)

    rows = (
        await db.execute(
            embedding_query,
            {"bill_id": bill_id, "min_score": min_score, "top_k": top_k},
        )
    ).fetchall()

    # Fallback to pre-computed bill_similarities if no embedding rows returned
    if not rows:
        logger.info(
            "No embedding found for bill %s, falling back to bill_similarities", bill_id
        )
        fallback_query = text("""
            SELECT
                CASE WHEN bill_id_a = :bill_id THEN bill_id_b ELSE bill_id_a END AS bill_id,
                similarity_score AS score
            FROM bill_similarities
            WHERE (bill_id_a = :bill_id OR bill_id_b = :bill_id)
              AND similarity_score > :min_score
            ORDER BY similarity_score DESC
            LIMIT :top_k
        """)
        rows = (
            await db.execute(
                fallback_query,
                {"bill_id": bill_id, "min_score": min_score, "top_k": top_k},
            )
        ).fetchall()

    if not rows:
        return SimilarBillsResponse(
            data=[],
            meta=MetaResponse(total_count=0, ai_enriched=False),
        )

    # Load full bill metadata for each matched bill
    matched_ids = [r.bill_id for r in rows]
    score_map = {r.bill_id: float(r.score) for r in rows}

    bills_result = await db.execute(select(Bill).where(Bill.id.in_(matched_ids)))
    bills_by_id = {b.id: b for b in bills_result.scalars().all()}

    # Optionally exclude same-jurisdiction results
    data: list[SimilarBillResult] = []
    for matched_id in matched_ids:
        matched_bill = bills_by_id.get(matched_id)
        if not matched_bill:
            continue
        if exclude_same_jurisdiction and matched_bill.jurisdiction_id == bill.jurisdiction_id:
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
    bill_a_text = _extract_bill_text(bill_a)
    bill_b_text = _extract_bill_text(bill_b)

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


def _extract_bill_text(bill: Bill) -> str:
    """Return the best available text for a bill, falling back to its title."""
    if bill.texts:
        for t in bill.texts:
            if t.content_text:
                return t.content_text
    return bill.title
