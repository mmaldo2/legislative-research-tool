"""Legislator/person endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.schemas.common import MetaResponse
from src.schemas.person import (
    PersonListResponse,
    PersonResponse,
    PersonStatsResponse,
    PersonVoteListResponse,
    PersonVoteResponse,
)
from src.services.person_service import (
    get_person,
    get_person_stats,
    get_person_votes,
    list_people,
)

router = APIRouter()


@router.get("/people", response_model=PersonListResponse)
async def list_people_endpoint(
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    party: str | None = Query(None, description="Filter by party"),
    chamber: str | None = Query(None, description="Filter by chamber (upper/lower)"),
    q: str | None = Query(None, description="Search by name"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> PersonListResponse:
    """List legislators with optional filters."""
    people, total = await list_people(
        db,
        jurisdiction=jurisdiction,
        party=party,
        chamber=chamber,
        q=q,
        page=page,
        per_page=per_page,
    )

    data = [
        PersonResponse(
            id=p.id,
            name=p.name,
            party=p.party,
            current_jurisdiction_id=p.current_jurisdiction_id,
            current_chamber=p.current_chamber,
            current_district=p.current_district,
            image_url=p.image_url,
        )
        for p in people
    ]

    latest = max((p.updated_at for p in people), default=None)

    return PersonListResponse(
        data=data,
        meta=MetaResponse(
            total_count=total,
            page=page,
            per_page=per_page,
            sources=["congress_legislators"],
            last_updated=latest.isoformat() if latest else None,
        ),
    )


@router.get("/people/{person_id}", response_model=PersonResponse)
async def get_person_endpoint(
    person_id: str,
    db: AsyncSession = Depends(get_session),
) -> PersonResponse:
    """Get a legislator by ID."""
    person = await get_person(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    return PersonResponse(
        id=person.id,
        name=person.name,
        party=person.party,
        current_jurisdiction_id=person.current_jurisdiction_id,
        current_chamber=person.current_chamber,
        current_district=person.current_district,
        image_url=person.image_url,
    )


@router.get("/people/{person_id}/votes", response_model=PersonVoteListResponse)
async def get_person_votes_endpoint(
    person_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> PersonVoteListResponse:
    """Get a legislator's voting record with bill context."""
    person = await get_person(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    rows, total = await get_person_votes(db, person_id, page=page, per_page=per_page)

    data = [
        PersonVoteResponse(
            vote_event_id=r.vote_event_id,
            bill_id=r.bill_id,
            bill_identifier=r.bill_identifier,
            bill_title=r.bill_title,
            vote_date=r.vote_date,
            chamber=r.chamber,
            motion_text=r.motion_text,
            result=r.result,
            option=r.option,
        )
        for r in rows
    ]

    return PersonVoteListResponse(
        data=data,
        meta=MetaResponse(total_count=total, page=page, per_page=per_page),
    )


@router.get("/people/{person_id}/stats", response_model=PersonStatsResponse)
async def get_person_stats_endpoint(
    person_id: str,
    db: AsyncSession = Depends(get_session),
) -> PersonStatsResponse:
    """Get aggregate statistics for a legislator."""
    person = await get_person(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    stats = await get_person_stats(db, person_id)
    return PersonStatsResponse(**stats)
