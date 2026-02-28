"""Bill CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import escape_like, get_session
from src.models.bill import Bill
from src.models.sponsorship import Sponsorship
from src.schemas.bill import (
    BillActionResponse,
    BillDetailResponse,
    BillListResponse,
    BillSummary,
    BillTextResponse,
    SponsorResponse,
)
from src.schemas.common import MetaResponse

router = APIRouter()


@router.get("/bills", response_model=BillListResponse)
async def list_bills(
    jurisdiction: str | None = Query(
        None, description="Filter by jurisdiction ID (e.g. us, us-ca)"
    ),
    session_id: str | None = Query(None, alias="session", description="Filter by session ID"),
    status: str | None = Query(None, description="Filter by bill status"),
    q: str | None = Query(None, description="Search title (case-insensitive contains)"),
    subject: str | None = Query(None, description="Filter by subject keyword"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> BillListResponse:
    """List bills with optional filters and pagination."""
    stmt = select(Bill)

    if jurisdiction:
        stmt = stmt.where(Bill.jurisdiction_id == jurisdiction)
    if session_id:
        stmt = stmt.where(Bill.session_id == session_id)
    if status:
        stmt = stmt.where(Bill.status == status)
    if q:
        stmt = stmt.where(Bill.title.ilike(f"%{escape_like(q)}%", escape="\\"))
    if subject:
        stmt = stmt.where(Bill.subject.any(subject))

    # Count total before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Apply pagination
    stmt = stmt.order_by(Bill.updated_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    bills = result.scalars().all()

    data = [
        BillSummary(
            id=b.id,
            jurisdiction_id=b.jurisdiction_id,
            session_id=b.session_id,
            identifier=b.identifier,
            title=b.title,
            status=b.status,
            status_date=b.status_date,
            classification=b.classification,
            subject=b.subject,
        )
        for b in bills
    ]

    return BillListResponse(
        data=data,
        meta=MetaResponse(
            total_count=total,
            page=page,
            per_page=per_page,
        ),
    )


@router.get("/bills/{bill_id}", response_model=BillDetailResponse)
async def get_bill(
    bill_id: str,
    db: AsyncSession = Depends(get_session),
) -> BillDetailResponse:
    """Get full bill detail including texts, actions, sponsors, and AI summary."""
    stmt = (
        select(Bill)
        .where(Bill.id == bill_id)
        .options(
            selectinload(Bill.texts),
            selectinload(Bill.actions),
            selectinload(Bill.sponsorships).selectinload(Sponsorship.person),
            selectinload(Bill.analyses),
        )
    )
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    # Find latest AI summary if one exists
    ai_summary = None
    for a in bill.analyses:
        if a.analysis_type == "summary":
            ai_summary = a.result
            break

    texts = [
        BillTextResponse(
            id=t.id,
            version_name=t.version_name,
            version_date=t.version_date,
            content_text=t.content_text,
            source_url=t.source_url,
            word_count=t.word_count,
        )
        for t in bill.texts
    ]

    actions = sorted(
        [
            BillActionResponse(
                action_date=a.action_date,
                description=a.description,
                classification=a.classification,
                chamber=a.chamber,
            )
            for a in bill.actions
        ],
        key=lambda a: a.action_date,
    )

    sponsors = [
        SponsorResponse(
            person_id=s.person_id,
            name=s.person.name,
            party=s.person.party,
            classification=s.classification,
        )
        for s in bill.sponsorships
    ]

    return BillDetailResponse(
        id=bill.id,
        jurisdiction_id=bill.jurisdiction_id,
        session_id=bill.session_id,
        identifier=bill.identifier,
        title=bill.title,
        status=bill.status,
        status_date=bill.status_date,
        classification=bill.classification,
        subject=bill.subject,
        source_urls=bill.source_urls,
        created_at=bill.created_at,
        updated_at=bill.updated_at,
        ai_summary=ai_summary,
        texts=texts,
        actions=actions,
        sponsors=sponsors,
    )
