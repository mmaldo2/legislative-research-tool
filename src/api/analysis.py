"""AI analysis endpoints — summarize and classify bills on demand."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_llm_harness, get_session
from src.models.bill import Bill
from src.schemas.analysis import BillSummaryOutput, TopicClassificationOutput

router = APIRouter()


class SummarizeRequest(BaseModel):
    bill_id: str


class ClassifyRequest(BaseModel):
    bill_id: str


@router.post("/analyze/summarize", response_model=BillSummaryOutput)
async def summarize_bill(
    req: SummarizeRequest,
    db: AsyncSession = Depends(get_session),
) -> BillSummaryOutput:
    """Generate an AI summary for a bill. Cached by content hash."""
    harness = await get_llm_harness(db)

    stmt = select(Bill).where(Bill.id == req.bill_id).options(selectinload(Bill.texts))
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    # Use the latest text version, fall back to title
    bill_text = bill.title
    if bill.texts:
        for t in bill.texts:
            if t.content_text:
                bill_text = t.content_text
                break

    output = await harness.summarize(
        bill_id=bill.id,
        bill_text=bill_text,
        identifier=bill.identifier,
        jurisdiction=bill.jurisdiction_id,
        title=bill.title,
    )
    await db.commit()
    return output


@router.post("/analyze/classify", response_model=TopicClassificationOutput)
async def classify_bill(
    req: ClassifyRequest,
    db: AsyncSession = Depends(get_session),
) -> TopicClassificationOutput:
    """Classify a bill into policy topics. Requires an existing summary."""
    harness = await get_llm_harness(db)

    stmt = select(Bill).where(Bill.id == req.bill_id).options(selectinload(Bill.analyses))
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    # Find existing summary to use for classification
    summary_text = bill.title
    for a in bill.analyses:
        if a.analysis_type == "summary" and a.result:
            summary_text = a.result.get("plain_english_summary", bill.title)
            break

    output = await harness.classify(
        bill_id=bill.id,
        identifier=bill.identifier,
        title=bill.title,
        summary=summary_text,
    )
    await db.commit()
    return output
