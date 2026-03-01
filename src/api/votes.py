"""Vote event endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_session
from src.models.vote import VoteEvent, VoteRecord
from src.schemas.common import MetaResponse
from src.schemas.vote import VoteEventListResponse, VoteEventResponse, VoteRecordResponse

router = APIRouter()


@router.get("/bills/{bill_id}/votes", response_model=VoteEventListResponse)
async def list_bill_votes(
    bill_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> VoteEventListResponse:
    """List vote events for a bill, including individual vote records."""
    stmt = (
        select(VoteEvent)
        .where(VoteEvent.bill_id == bill_id)
        .options(selectinload(VoteEvent.records).selectinload(VoteRecord.person))
    )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(VoteEvent.vote_date.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    events = result.scalars().unique().all()

    data = [
        VoteEventResponse(
            id=ve.id,
            bill_id=ve.bill_id,
            vote_date=ve.vote_date,
            chamber=ve.chamber,
            motion_text=ve.motion_text,
            result=ve.result,
            yes_count=ve.yes_count,
            no_count=ve.no_count,
            other_count=ve.other_count,
            records=[
                VoteRecordResponse(
                    person_id=r.person_id,
                    person_name=r.person.name if r.person else None,
                    option=r.option,
                )
                for r in ve.records
            ],
        )
        for ve in events
    ]

    return VoteEventListResponse(
        data=data,
        meta=MetaResponse(total_count=total, page=page, per_page=per_page),
    )
