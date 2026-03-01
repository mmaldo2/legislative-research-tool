"""Bill query service — encapsulates all bill-related DB queries."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import escape_like
from src.models.bill import Bill
from src.models.sponsorship import Sponsorship


async def list_bills(
    session: AsyncSession,
    *,
    jurisdiction: str | None = None,
    session_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
    subject: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Bill], int]:
    """Query bills with filters and pagination. Returns (bills, total_count)."""
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

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Bill.updated_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(stmt)
    bills = result.scalars().all()

    return bills, total


async def get_bill_detail(session: AsyncSession, bill_id: str) -> Bill | None:
    """Fetch a single bill with all related data eagerly loaded."""
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
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
