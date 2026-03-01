"""AI analysis endpoints — summarize, classify, version diff, constitutional, patterns."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_llm_harness, get_session, limiter
from src.llm.harness import LLMHarness
from src.models.ai_analysis import AiAnalysis
from src.models.bill import Bill
from src.models.bill_text import texts_without_markup
from src.models.sponsorship import Sponsorship
from src.schemas.analysis import (
    AnalysisListResponse,
    AnalysisResponse,
    BillSummaryOutput,
    ClassifyRequest,
    ConstitutionalAnalysisOutput,
    ConstitutionalRequest,
    DiffusionEvent,
    DiffusionOutput,
    PatternDetectionOutput,
    PatternDetectRequest,
    PredictionOutput,
    PredictRequest,
    SummarizeRequest,
    TopicClassificationOutput,
    VersionDiffOutput,
    VersionDiffRequest,
)
from src.schemas.common import MetaResponse
from src.search.vector import find_similar_bill_ids
from src.services.bill_service import extract_bill_text

logger = logging.getLogger(__name__)

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
    stmt = select(Bill).where(Bill.id == req.bill_id).options(texts_without_markup(Bill.texts))
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    bill_text = extract_bill_text(bill)

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


@router.post("/analyze/version-diff", response_model=VersionDiffOutput)
@limiter.limit("10/minute")
async def version_diff(
    request: Request,
    req: VersionDiffRequest,
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
) -> VersionDiffOutput:
    """Analyze differences between two versions of the same bill."""
    stmt = select(Bill).where(Bill.id == req.bill_id).options(texts_without_markup(Bill.texts))
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    if len(bill.texts) < 2:
        raise HTTPException(
            status_code=400,
            detail="Bill must have at least 2 text versions for diff analysis",
        )

    # Sort texts by date (oldest first)
    sorted_texts = sorted(
        [t for t in bill.texts if t.content_text],
        key=lambda t: t.version_date or t.created_at,
    )
    if len(sorted_texts) < 2:
        raise HTTPException(
            status_code=400,
            detail="Bill must have at least 2 text versions with content",
        )

    # Resolve version A (default: first/oldest)
    if req.version_a_id:
        version_a = next((t for t in sorted_texts if t.id == req.version_a_id), None)
        if not version_a:
            raise HTTPException(status_code=404, detail="Version A text not found")
    else:
        version_a = sorted_texts[0]

    # Resolve version B (default: latest)
    if req.version_b_id:
        version_b = next((t for t in sorted_texts if t.id == req.version_b_id), None)
        if not version_b:
            raise HTTPException(status_code=404, detail="Version B text not found")
    else:
        version_b = sorted_texts[-1]

    # Guard: versions must be different
    if version_a.id == version_b.id:
        raise HTTPException(
            status_code=400,
            detail="Version A and Version B must be different text versions",
        )

    output = await harness.version_diff(
        bill_id=bill.id,
        identifier=bill.identifier,
        jurisdiction=bill.jurisdiction_id,
        version_a_name=version_a.version_name or "Earlier Version",
        version_a_text=version_a.content_text,
        version_b_name=version_b.version_name or "Later Version",
        version_b_text=version_b.content_text,
    )
    await db.commit()
    return output


@router.post("/analyze/constitutional", response_model=ConstitutionalAnalysisOutput)
@limiter.limit("10/minute")
async def constitutional_analysis(
    request: Request,
    req: ConstitutionalRequest,
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
) -> ConstitutionalAnalysisOutput:
    """Analyze a bill for potential constitutional concerns."""
    stmt = select(Bill).where(Bill.id == req.bill_id).options(texts_without_markup(Bill.texts))
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    bill_text = extract_bill_text(bill)

    output = await harness.constitutional_analysis(
        bill_id=bill.id,
        bill_text=bill_text,
        identifier=bill.identifier,
        jurisdiction=bill.jurisdiction_id,
        title=bill.title,
    )
    await db.commit()
    return output


@router.post("/analyze/patterns", response_model=PatternDetectionOutput)
@limiter.limit("5/minute")
async def pattern_detect(
    request: Request,
    req: PatternDetectRequest,
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
) -> PatternDetectionOutput:
    """Detect cross-jurisdictional patterns and model legislation for a bill."""
    stmt = select(Bill).where(Bill.id == req.bill_id).options(texts_without_markup(Bill.texts))
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    source_text = extract_bill_text(bill)

    # Find similar bills from other jurisdictions
    matches = await find_similar_bill_ids(
        db,
        req.bill_id,
        exclude_jurisdiction=bill.jurisdiction_id,
        top_k=req.top_k,
    )
    if not matches:
        raise HTTPException(
            status_code=400,
            detail="No similar bills found in other jurisdictions for pattern analysis",
        )

    # Load similar bills with texts
    matched_ids = [m.bill_id for m in matches]
    bills_result = await db.execute(
        select(Bill).where(Bill.id.in_(matched_ids)).options(texts_without_markup(Bill.texts))
    )
    similar_bills = bills_result.scalars().all()

    # Format similar bills text for the prompt
    similar_parts: list[str] = []
    for sb in similar_bills:
        sb_text = extract_bill_text(sb)
        similar_parts.append(
            f"Bill: {sb.identifier}\n"
            f"Jurisdiction: {sb.jurisdiction_id}\n"
            f"Title: {sb.title}\n"
            f"Text:\n{sb_text[:10000]}\n"
        )

    similar_bills_text = "\n---\n".join(similar_parts)

    output = await harness.pattern_detect(
        source_bill_id=bill.id,
        source_text=source_text,
        source_identifier=bill.identifier,
        source_jurisdiction=bill.jurisdiction_id,
        source_title=bill.title,
        similar_bills_text=similar_bills_text,
    )
    await db.commit()
    return output


@router.get("/analyze/diffusion/{bill_id}", response_model=DiffusionOutput)
@limiter.limit("10/minute")
async def policy_diffusion(
    request: Request,
    bill_id: str,
    top_k: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_session),
) -> DiffusionOutput:
    """Track how a legislative idea spread across jurisdictions over time."""
    # Load the source bill
    result = await db.execute(select(Bill).where(Bill.id == bill_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Bill not found")

    # Find similar bills from other jurisdictions
    matches = await find_similar_bill_ids(
        db, bill_id, exclude_jurisdiction=source.jurisdiction_id, top_k=top_k
    )
    if not matches:
        return DiffusionOutput(
            source_bill_id=source.id,
            source_identifier=source.identifier,
            source_jurisdiction=source.jurisdiction_id,
            source_date=str(source.status_date) if source.status_date else None,
            timeline=[],
            total_jurisdictions=0,
            summary="No similar bills found in other jurisdictions.",
            confidence=1.0,
        )

    # Load matched bills with status dates
    matched_ids = [m.bill_id for m in matches]
    score_map = {m.bill_id: m.score for m in matches}
    bills_result = await db.execute(
        select(Bill).where(Bill.id.in_(matched_ids))
    )
    similar_bills = bills_result.scalars().all()

    # Build timeline sorted by status_date
    events = []
    for b in similar_bills:
        events.append(
            DiffusionEvent(
                bill_id=b.id,
                identifier=b.identifier,
                jurisdiction_id=b.jurisdiction_id,
                title=b.title,
                status=b.status,
                status_date=str(b.status_date) if b.status_date else None,
                similarity_score=score_map.get(b.id, 0.0),
            )
        )

    # Sort by date (None dates go last)
    events.sort(key=lambda e: e.status_date or "9999-99-99")

    jurisdictions = list({e.jurisdiction_id for e in events})
    dates = [e.status_date for e in events if e.status_date]

    return DiffusionOutput(
        source_bill_id=source.id,
        source_identifier=source.identifier,
        source_jurisdiction=source.jurisdiction_id,
        source_date=str(source.status_date) if source.status_date else None,
        timeline=events,
        total_jurisdictions=len(jurisdictions),
        earliest_date=min(dates) if dates else None,
        latest_date=max(dates) if dates else None,
        summary=(
            f"Found {len(events)} similar bills across {len(jurisdictions)} jurisdictions."
        ),
        confidence=0.8,
    )


@router.post("/analyze/predict", response_model=PredictionOutput)
@limiter.limit("5/minute")
async def predict_outcome(
    request: Request,
    req: PredictRequest,
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
) -> PredictionOutput:
    """Predict the likely outcome of a bill based on its features."""
    stmt = (
        select(Bill)
        .where(Bill.id == req.bill_id)
        .options(
            selectinload(Bill.sponsorships).selectinload(Sponsorship.person),
            selectinload(Bill.actions),
        )
    )
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    # Format sponsors
    sponsor_lines = []
    for s in bill.sponsorships:
        if not s.person:
            continue
        party = s.person.party or "Unknown"
        sponsor_lines.append(f"- {s.person.name} ({party}) [{s.classification}]")
    sponsors_text = "\n".join(sponsor_lines) if sponsor_lines else "None listed"

    # Format actions (most recent first)
    sorted_actions = sorted(
        [a for a in bill.actions if a.action_date],
        key=lambda a: a.action_date,
        reverse=True,
    )
    action_lines = []
    for a in sorted_actions[:20]:
        action_lines.append(f"- {a.action_date}: {a.description}")
    actions_text = "\n".join(action_lines) if action_lines else "No actions recorded"

    subjects = ", ".join(bill.subject) if bill.subject else "None"
    classification = ", ".join(bill.classification) if bill.classification else "bill"
    session_info = bill.session_id or "Unknown session"

    output = await harness.predict_outcome(
        bill_id=bill.id,
        identifier=bill.identifier,
        jurisdiction=bill.jurisdiction_id,
        title=bill.title,
        status=bill.status or "unknown",
        classification=classification,
        sponsors_text=sponsors_text,
        sponsor_count=len(bill.sponsorships),
        actions_text=actions_text,
        action_count=len(bill.actions),
        subjects=subjects,
        session_info=session_info,
    )
    await db.commit()
    return output


@router.get("/analyses", response_model=AnalysisListResponse)
async def list_analyses(
    bill_id: str | None = Query(None, description="Filter by bill ID"),
    analysis_type: str | None = Query(
        None,
        description="Filter by type: summary, topics, comparison, "
        "version_diff, constitutional, pattern_detect",
    ),
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
