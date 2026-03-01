"""Jurisdiction query service."""

from sqlalchemy import desc, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bill import Bill
from src.models.person import Person
from src.models.session import LegislativeSession


async def get_jurisdiction_stats(
    session: AsyncSession,
    jurisdiction_id: str,
) -> dict:
    """Compute aggregate stats for a jurisdiction."""
    # Total bills
    total_bills_stmt = select(func.count()).where(Bill.jurisdiction_id == jurisdiction_id)
    total_bills = (await session.execute(total_bills_stmt)).scalar_one()

    # Total legislators
    total_legislators_stmt = select(func.count()).where(
        Person.current_jurisdiction_id == jurisdiction_id
    )
    total_legislators = (await session.execute(total_legislators_stmt)).scalar_one()

    # Bills by status
    status_stmt = (
        select(Bill.status, func.count().label("cnt"))
        .where(Bill.jurisdiction_id == jurisdiction_id, Bill.status.is_not(None))
        .group_by(Bill.status)
    )
    status_rows = (await session.execute(status_stmt)).all()
    bills_by_status = {row.status: row.cnt for row in status_rows}

    # Bills by session
    session_stmt = (
        select(
            LegislativeSession.id,
            LegislativeSession.name,
            func.count(Bill.id).label("bill_count"),
        )
        .join(Bill, Bill.session_id == LegislativeSession.id)
        .where(LegislativeSession.jurisdiction_id == jurisdiction_id)
        .group_by(LegislativeSession.id, LegislativeSession.name)
        .order_by(LegislativeSession.start_date.desc().nullslast())
    )
    session_rows = (await session.execute(session_stmt)).all()
    bills_by_session = [
        {"session_id": r.id, "session_name": r.name, "bill_count": r.bill_count}
        for r in session_rows
    ]

    # Top subjects (unnest ARRAY column)
    subject_stmt = (
        select(
            func.unnest(Bill.subject).label("subj"),
            func.count().label("cnt"),
        )
        .where(Bill.jurisdiction_id == jurisdiction_id, Bill.subject.is_not(None))
        .group_by(literal_column("subj"))
        .order_by(desc("cnt"))
        .limit(15)
    )
    subject_rows = (await session.execute(subject_stmt)).all()
    top_subjects = [{"subject": r.subj, "count": r.cnt} for r in subject_rows]

    return {
        "total_bills": total_bills,
        "total_legislators": total_legislators,
        "bills_by_status": bills_by_status,
        "bills_by_session": bills_by_session,
        "top_subjects": top_subjects,
    }
