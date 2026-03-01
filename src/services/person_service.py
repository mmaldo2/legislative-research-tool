"""Person/legislator query service."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import escape_like
from src.models.bill import Bill
from src.models.person import Person
from src.models.sponsorship import Sponsorship
from src.models.vote import VoteEvent, VoteRecord


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


async def get_person_votes(
    session: AsyncSession,
    person_id: str,
    *,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list, int]:
    """Get vote records for a person with bill context. Returns (rows, total)."""
    base = (
        select(
            VoteRecord.option,
            VoteEvent.id.label("vote_event_id"),
            VoteEvent.vote_date,
            VoteEvent.chamber,
            VoteEvent.motion_text,
            VoteEvent.result,
            Bill.id.label("bill_id"),
            Bill.identifier.label("bill_identifier"),
            Bill.title.label("bill_title"),
        )
        .join(VoteEvent, VoteRecord.vote_event_id == VoteEvent.id)
        .join(Bill, VoteEvent.bill_id == Bill.id)
        .where(VoteRecord.person_id == person_id)
    )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = base.order_by(VoteEvent.vote_date.desc().nullslast())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(stmt)
    rows = result.all()

    return rows, total


async def get_person_stats(
    session: AsyncSession,
    person_id: str,
) -> dict:
    """Compute aggregate stats for a person."""
    # Count primary sponsorships
    sponsored_stmt = select(func.count()).where(
        Sponsorship.person_id == person_id,
        Sponsorship.classification == "primary",
    )
    bills_sponsored = (await session.execute(sponsored_stmt)).scalar_one()

    # Count cosponsorships
    cosponsored_stmt = select(func.count()).where(
        Sponsorship.person_id == person_id,
        Sponsorship.classification != "primary",
    )
    bills_cosponsored = (await session.execute(cosponsored_stmt)).scalar_one()

    # Count votes cast
    votes_stmt = select(func.count()).where(VoteRecord.person_id == person_id)
    votes_cast = (await session.execute(votes_stmt)).scalar_one()

    # Vote participation rate: votes cast / total vote events in person's jurisdiction
    person = await get_person(session, person_id)
    participation_rate = None
    if person and person.current_jurisdiction_id and votes_cast > 0:
        total_events_stmt = (
            select(func.count())
            .select_from(VoteEvent)
            .join(Bill, VoteEvent.bill_id == Bill.id)
            .where(Bill.jurisdiction_id == person.current_jurisdiction_id)
        )
        total_events = (await session.execute(total_events_stmt)).scalar_one()
        if total_events > 0:
            participation_rate = round(votes_cast / total_events, 4)

    return {
        "bills_sponsored": bills_sponsored,
        "bills_cosponsored": bills_cosponsored,
        "votes_cast": votes_cast,
        "vote_participation_rate": participation_rate,
    }
