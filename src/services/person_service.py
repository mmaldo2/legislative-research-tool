"""Person/legislator query service."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import escape_like
from src.models.person import Person


async def list_people(
    session: AsyncSession,
    *,
    jurisdiction: str | None = None,
    party: str | None = None,
    chamber: str | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Person], int]:
    """Query people with filters and pagination. Returns (people, total_count)."""
    stmt = select(Person)

    if jurisdiction:
        stmt = stmt.where(Person.current_jurisdiction_id == jurisdiction)
    if party:
        stmt = stmt.where(Person.party == party)
    if chamber:
        stmt = stmt.where(Person.current_chamber == chamber)
    if q:
        stmt = stmt.where(Person.name.ilike(f"%{escape_like(q)}%", escape="\\"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Person.name)
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(stmt)
    people = result.scalars().all()

    return people, total


async def get_person(session: AsyncSession, person_id: str) -> Person | None:
    """Fetch a single person by ID."""
    result = await session.execute(select(Person).where(Person.id == person_id))
    return result.scalar_one_or_none()
