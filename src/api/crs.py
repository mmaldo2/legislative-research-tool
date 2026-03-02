"""CRS report API endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import escape_like, get_session
from src.models.crs_report import CrsReport
from src.schemas.common import MetaResponse
from src.schemas.crs import CrsReportListResponse, CrsReportResponse

router = APIRouter()


@router.get("/crs-reports", response_model=CrsReportListResponse)
async def list_crs_reports(
    topic: str | None = Query(None, description="Filter by topic (case-insensitive contains)"),
    q: str | None = Query(None, description="Search title/summary (case-insensitive contains)"),
    author: str | None = Query(None, description="Filter by author name (case-insensitive)"),
    related_bill: str | None = Query(
        None, description="Filter by related bill identifier (e.g. 'HR 1234')"
    ),
    date_from: date | None = Query(None, description="Reports published on or after this date"),
    date_to: date | None = Query(None, description="Reports published on or before this date"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> CrsReportListResponse:
    """List and search CRS reports with optional filters."""
    query = select(CrsReport)
    count_query = select(func.count(CrsReport.id))

    # Topic filter — JSONB array contains (cast topic list to text for ILIKE)
    if topic:
        safe_topic = escape_like(topic)
        topic_filter = func.cast(CrsReport.topics, type_=func.text()).ilike(f"%{safe_topic}%")
        query = query.where(topic_filter)
        count_query = count_query.where(topic_filter)

    # Full-text search on title + summary
    if q:
        safe_q = escape_like(q)
        text_filter = CrsReport.title.ilike(f"%{safe_q}%") | CrsReport.summary.ilike(f"%{safe_q}%")
        query = query.where(text_filter)
        count_query = count_query.where(text_filter)

    # Author filter — JSONB array contains
    if author:
        safe_author = escape_like(author)
        author_filter = func.cast(CrsReport.authors, type_=func.text()).ilike(f"%{safe_author}%")
        query = query.where(author_filter)
        count_query = count_query.where(author_filter)

    # Related bill filter — JSONB array contains
    if related_bill:
        safe_bill = escape_like(related_bill)
        bill_filter = func.cast(CrsReport.related_bill_ids, type_=func.text()).ilike(
            f"%{safe_bill}%"
        )
        query = query.where(bill_filter)
        count_query = count_query.where(bill_filter)

    # Date range filters
    if date_from:
        date_from_filter = CrsReport.most_recent_date >= date_from
        query = query.where(date_from_filter)
        count_query = count_query.where(date_from_filter)

    if date_to:
        date_to_filter = CrsReport.most_recent_date <= date_to
        query = query.where(date_to_filter)
        count_query = count_query.where(date_to_filter)

    # Get total count
    total = await db.scalar(count_query) or 0

    # Paginate and order by most recent first
    offset = (page - 1) * per_page
    query = (
        query.order_by(CrsReport.most_recent_date.desc().nullslast(), CrsReport.id)
        .offset(offset)
        .limit(per_page)
    )

    result = await db.execute(query)
    reports = result.scalars().all()

    data = [
        CrsReportResponse(
            id=r.id,
            title=r.title,
            summary=r.summary,
            authors=r.authors,
            topics=r.topics,
            publication_date=r.publication_date,
            most_recent_date=r.most_recent_date,
            source_url=r.source_url,
            pdf_url=r.pdf_url,
            related_bill_ids=r.related_bill_ids,
            content_text=None,  # Omit full text from list view
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in reports
    ]

    latest = max((r.updated_at or r.created_at for r in reports), default=None)

    return CrsReportListResponse(
        data=data,
        meta=MetaResponse(
            total_count=total,
            page=page,
            per_page=per_page,
            sources=["everycrsreport"],
            last_updated=latest.isoformat() if latest else None,
        ),
    )


@router.get("/crs-reports/{report_id}", response_model=CrsReportResponse)
async def get_crs_report(
    report_id: str,
    db: AsyncSession = Depends(get_session),
) -> CrsReportResponse:
    """Get a single CRS report by its report number."""
    result = await db.execute(select(CrsReport).where(CrsReport.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="CRS report not found")

    return CrsReportResponse(
        id=report.id,
        title=report.title,
        summary=report.summary,
        authors=report.authors,
        topics=report.topics,
        publication_date=report.publication_date,
        most_recent_date=report.most_recent_date,
        source_url=report.source_url,
        pdf_url=report.pdf_url,
        related_bill_ids=report.related_bill_ids,
        content_text=report.content_text,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )
