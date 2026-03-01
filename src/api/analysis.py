"""AI analysis endpoints — summarize, classify, version diff, constitutional, patterns."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, text
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
    ConstitutionalAnalysisOutput,
    ConstitutionalRequest,
    PatternDetectionOutput,
    PatternDetectRequest,
    SummarizeRequest,
    TopicClassificationOutput,
    VersionDiffOutput,
    VersionDiffRequest,
)
from src.schemas.common import MetaResponse

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


@router.post("/analyze/version-diff", response_model=VersionDiffOutput)
@limiter.limit("10/minute")
async def version_diff(
    request: Request,
    req: VersionDiffRequest,
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
) -> VersionDiffOutput:
    """Analyze differences between two versions of the same bill."""
    stmt = select(Bill).where(Bill.id == req.bill_id).options(selectinload(Bill.texts))
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

    output = await harness.version_diff(
        bill_id=bill.id,
        identifier=bill.identifier,
        jurisdiction=bill.jurisdiction_id,
        version_a_name=version_a.version_name,
        version_a_text=version_a.content_text,
        version_b_name=version_b.version_name,
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
    stmt = select(Bill).where(Bill.id == req.bill_id).options(selectinload(Bill.texts))
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    bill_text = bill.title
    if bill.texts:
        for t in bill.texts:
            if t.content_text:
                bill_text = t.content_text
                break

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
    stmt = select(Bill).where(Bill.id == req.bill_id).options(selectinload(Bill.texts))
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    source_text = bill.title
    if bill.texts:
        for t in bill.texts:
            if t.content_text:
                source_text = t.content_text
                break

    # Find similar bills via pgvector, excluding same jurisdiction
    similar_query = text("""
        SELECT be2.bill_id, 1 - (be1.embedding <=> be2.embedding) AS score
        FROM bill_embeddings be1
        JOIN bill_embeddings be2 ON be1.bill_id != be2.bill_id
        JOIN bills b ON b.id = be2.bill_id
        WHERE be1.bill_id = :bill_id
          AND b.jurisdiction_id != :jurisdiction
        ORDER BY be1.embedding <=> be2.embedding
        LIMIT :top_k
    """)
    rows = (
        await db.execute(
            similar_query,
            {"bill_id": req.bill_id, "jurisdiction": bill.jurisdiction_id, "top_k": req.top_k},
        )
    ).fetchall()

    if not rows:
        # Fallback to bill_similarities table
        fallback_query = text("""
            SELECT
                CASE WHEN bill_id_a = :bill_id THEN bill_id_b
                     ELSE bill_id_a END AS bill_id,
                similarity_score AS score
            FROM bill_similarities bs
            JOIN bills b ON b.id = (
                CASE WHEN bs.bill_id_a = :bill_id THEN bs.bill_id_b
                     ELSE bs.bill_id_a END
            )
            WHERE (bs.bill_id_a = :bill_id OR bs.bill_id_b = :bill_id)
              AND b.jurisdiction_id != :jurisdiction
            ORDER BY bs.similarity_score DESC
            LIMIT :top_k
        """)
        rows = (
            await db.execute(
                fallback_query,
                {
                    "bill_id": req.bill_id,
                    "jurisdiction": bill.jurisdiction_id,
                    "top_k": req.top_k,
                },
            )
        ).fetchall()

    if not rows:
        raise HTTPException(
            status_code=400,
            detail="No similar bills found in other jurisdictions for pattern analysis",
        )

    # Load similar bills with texts
    matched_ids = [r.bill_id for r in rows]
    bills_result = await db.execute(
        select(Bill).where(Bill.id.in_(matched_ids)).options(selectinload(Bill.texts))
    )
    similar_bills = bills_result.scalars().all()

    # Format similar bills text for the prompt
    similar_parts: list[str] = []
    for sb in similar_bills:
        sb_text = sb.title
        if sb.texts:
            for t in sb.texts:
                if t.content_text:
                    sb_text = t.content_text
                    break
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
