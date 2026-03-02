"""Committee hearing CRUD endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.schemas.common import MetaResponse
from src.schemas.hearing import HearingListResponse, HearingResponse
from src.services.hearing_service import (
    get_hearing_detail,
    list_hearings,
    list_hearings_for_bill,
)

router = APIRouter()


def _hearing_to_response(h) -> HearingResponse:
    """Convert a CommitteeHearing ORM model to a HearingResponse."""
    linked_bill_ids = [link.bill_id for link in h.bill_links] if h.bill_links else []
    return HearingResponse(
        id=h.id,
        bill_id=h.bill_id,
        committee_name=h.committee_name,
        committee_code=h.committee_code,
        chamber=h.chamber,
        title=h.title,
        hearing_date=h.hearing_date,
        location=h.location,
        url=h.url,
        congress=h.congress,
        created_at=h.created_at,
        linked_bill_ids=linked_bill_ids,
    )


@router.get("/hearings", response_model=HearingListResponse)
async def list_hearings_endpoint(
    committee: str | None = Query(None, description="Filter by committee name (partial match)"),
    chamber: str | None = Query(None, description="Filter by chamber: senate, house, joint"),
    congress: int | None = Query(None, description="Filter by congress number"),
    bill_id: str | None = Query(None, description="Filter hearings linked to a specific bill"),
    date_from: date | None = Query(None, description="Start date filter (inclusive)"),
    date_to: date | None = Query(None, description="End date filter (inclusive)"),
    q: str | None = Query(None, description="Search hearing title (case-insensitive)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> HearingListResponse:
    """List committee hearings with optional filters and pagination."""
    hearings, total = await list_hearings(
        db,
        committee=committee,
        chamber=chamber,
        congress=congress,
        bill_id=bill_id,
        date_from=date_from,
        date_to=date_to,
        q=q,
        page=page,
        per_page=per_page,
    )

    data = [_hearing_to_response(h) for h in hearings]

    return HearingListResponse(
        data=data,
        meta=MetaResponse(
            total_count=total,
            page=page,
            per_page=per_page,
            sources=["congress_gov"],
        ),
    )


@router.get("/hearings/{hearing_id}", response_model=HearingResponse)
async def get_hearing_endpoint(
    hearing_id: str,
    db: AsyncSession = Depends(get_session),
) -> HearingResponse:
    """Get full committee hearing detail."""
    hearing = await get_hearing_detail(db, hearing_id)
    if not hearing:
        raise HTTPException(status_code=404, detail="Hearing not found")
    return _hearing_to_response(hearing)


@router.get("/bills/{bill_id}/hearings", response_model=HearingListResponse)
async def list_bill_hearings_endpoint(
    bill_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> HearingListResponse:
    """List all committee hearings linked to a specific bill."""
    hearings, total = await list_hearings_for_bill(db, bill_id, page=page, per_page=per_page)

    data = [_hearing_to_response(h) for h in hearings]

    return HearingListResponse(
        data=data,
        meta=MetaResponse(
            total_count=total,
            page=page,
            per_page=per_page,
            sources=["congress_gov"],
        ),
    )
