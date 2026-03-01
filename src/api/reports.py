"""Automated research report generation endpoint."""

import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_llm_harness, get_session, limiter
from src.llm.harness import LLMHarness
from src.models.bill import Bill
from src.models.bill_text import texts_without_markup
from src.schemas.analysis import ReportOutput, ReportRequest
from src.search.engine import hybrid_search
from src.services.bill_service import extract_bill_text

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/reports/generate", response_model=ReportOutput)
@limiter.limit("3/minute")
async def generate_report(
    request: Request,
    req: ReportRequest,
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
) -> ReportOutput:
    """Generate a multi-bill research report from a search query."""
    # Search for matching bills
    results = await hybrid_search(
        session=db,
        query=req.query,
        jurisdiction=req.jurisdiction,
        top_k=req.max_bills,
    )

    if not results:
        raise HTTPException(
            status_code=400,
            detail="No bills found matching the query. Try broader search terms.",
        )

    # Load full bill data with texts
    bill_ids = [r[0] for r in results]
    stmt = (
        select(Bill)
        .where(Bill.id.in_(bill_ids))
        .options(texts_without_markup(Bill.texts))
    )
    db_result = await db.execute(stmt)
    bills = db_result.scalars().all()

    if not bills:
        raise HTTPException(status_code=400, detail="No bill data available for report.")

    # Format bills text for the LLM prompt
    bill_parts: list[str] = []
    jurisdictions: set[str] = set()
    for bill in bills:
        jurisdictions.add(bill.jurisdiction_id)
        text = extract_bill_text(bill)
        bill_parts.append(
            f"Bill: {bill.identifier}\n"
            f"Jurisdiction: {bill.jurisdiction_id}\n"
            f"Title: {bill.title}\n"
            f"Status: {bill.status or 'unknown'}\n"
            f"Text:\n{text[:5000]}\n"
        )

    bills_text = "\n---\n".join(bill_parts)

    # Synthetic report ID for caching (hash of query + jurisdiction + max_bills)
    report_key = f"report:{req.query}:{req.jurisdiction or 'all'}:{req.max_bills}"
    report_id = hashlib.sha256(report_key.encode()).hexdigest()[:16]

    output = await harness.generate_report(
        report_id=report_id,
        query=req.query,
        bills_text=bills_text,
        bill_count=len(bills),
        jurisdiction_count=len(jurisdictions),
        jurisdiction_filter=req.jurisdiction,
    )

    await db.commit()
    return output
