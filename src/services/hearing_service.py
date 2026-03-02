"""Hearing query service — encapsulates all committee-hearing-related DB queries."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import escape_like
from src.models.committee_hearing import CommitteeHearing, HearingBillLink


async def list_hearings(
    session: AsyncSession,
    *,
    committee: str | None = None,
    chamber: str | None = None,
    congress: int | None = None,
    bill_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[CommitteeHearing], int]:
    """Query hearings with filters and pagination. Returns (hearings, total_count)."""
    stmt = select(CommitteeHearing).options(selectinload(CommitteeHearing.bill_links))

    if committee:
        stmt = stmt.where(
            CommitteeHearing.committee_name.ilike(f"%{escape_like(committee)}%", escape="\\")
        )
    if chamber:
        stmt = stmt.where(CommitteeHearing.chamber == chamber.lower())
    if congress:
        stmt = stmt.where(CommitteeHearing.congress == congress)
    if bill_id:
        stmt = stmt.join(HearingBillLink).where(HearingBillLink.bill_id == bill_id)
    if date_from:
        stmt = stmt.where(CommitteeHearing.hearing_date >= date_from)
    if date_to:
        stmt = stmt.where(CommitteeHearing.hearing_date <= date_to)
    if q:
        stmt = stmt.where(CommitteeHearing.title.ilike(f"%{escape_like(q)}%", escape="\\"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(CommitteeHearing.hearing_date.desc().nullslast())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(stmt)
    hearings = result.scalars().unique().all()

    return list(hearings), total


async def get_hearing_detail(session: AsyncSession, hearing_id: str) -> CommitteeHearing | None:
    """Fetch a single hearing with bill links eagerly loaded."""
    stmt = (
        select(CommitteeHearing)
        .where(CommitteeHearing.id == hearing_id)
        .options(selectinload(CommitteeHearing.bill_links))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_hearings_for_bill(
    session: AsyncSession,
    bill_id: str,
    *,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[CommitteeHearing], int]:
    """Fetch all hearings linked to a specific bill."""
    stmt = (
        select(CommitteeHearing)
        .join(HearingBillLink)
        .where(HearingBillLink.bill_id == bill_id)
        .options(selectinload(CommitteeHearing.bill_links))
    )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(CommitteeHearing.hearing_date.desc().nullslast())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(stmt)
    hearings = result.scalars().unique().all()

    return list(hearings), total
