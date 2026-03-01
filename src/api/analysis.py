"""AI analysis endpoints — summarize, classify, and browse analyses."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_llm_harness, get_session, limiter
from src.llm.harness import LLMHarness
from src.models.ai_analysis import AiAnalysis
from src.models.bill import Bill
from src.schemas.analysis import (
    AnalysisListResponse,
    AnalysisResponse,
    BillSummaryOutput,
    ClassifyRequest,
    SummarizeRequest,
    TopicClassificationOutput,
)
from src.schemas.common import MetaResponse

router = APIRouter()


@router.post("/analyze/summarize", response_model=BillSummaryOutput)
@limiter.limit("10/minute")
async def summarize_bill(
    request: Request,
    req: SummarizeRequest,
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
) -> BillSummaryOutput:
    """Generate an AI summary for a bill. Cached by content hash."""
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
@limiter.limit("10/minute")
async def classify_bill(
    request: Request,
    req: ClassifyRequest,
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
) -> TopicClassificationOutput:
    """Classify a bill into policy topics. Requires an existing summary."""
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


@router.get("/analyses", response_model=AnalysisListResponse)
async def list_analyses(
    bill_id: str | None = Query(None, description="Filter by bill ID"),
    analysis_type: str | None = Query(None, description="Filter by type (summary, classification)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> AnalysisListResponse:
    """List stored AI analyses with optional filters."""
    stmt = select(AiAnalysis)
    if bill_id:
        stmt = stmt.where(AiAnalysis.bill_id == bill_id)
    if analysis_type:
        stmt = stmt.where(AiAnalysis.analysis_type == analysis_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(AiAnalysis.created_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    analyses = result.scalars().all()

    data = [
        AnalysisResponse(
            id=a.id,
            bill_id=a.bill_id,
            analysis_type=a.analysis_type,
            result=a.result,
            model_used=a.model_used,
            prompt_version=a.prompt_version,
            confidence=a.confidence,
            tokens_input=a.tokens_input,
            tokens_output=a.tokens_output,
            cost_usd=a.cost_usd,
            created_at=a.created_at,
        )
        for a in analyses
    ]

    return AnalysisListResponse(
        data=data,
        meta=MetaResponse(
            total_count=total,
            page=page,
            per_page=per_page,
            ai_enriched=True,
        ),
    )


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: int,
    db: AsyncSession = Depends(get_session),
) -> AnalysisResponse:
    """Get a specific AI analysis by ID."""
    result = await db.execute(select(AiAnalysis).where(AiAnalysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return AnalysisResponse(
        id=analysis.id,
        bill_id=analysis.bill_id,
        analysis_type=analysis.analysis_type,
        result=analysis.result,
        model_used=analysis.model_used,
        prompt_version=analysis.prompt_version,
        confidence=analysis.confidence,
        tokens_input=analysis.tokens_input,
        tokens_output=analysis.tokens_output,
        cost_usd=analysis.cost_usd,
        created_at=analysis.created_at,
    )
