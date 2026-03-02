"""Saved search CRUD endpoints with alert subscription management."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session, limiter, require_api_key, require_org
from src.models.alert_subscription import AlertSubscription
from src.models.saved_search import SavedSearch
from src.models.webhook_endpoint import WebhookEndpoint
from src.schemas.saved_search import (
    AlertSubscriptionCreate,
    AlertSubscriptionResponse,
    SavedSearchCreate,
    SavedSearchResponse,
    SavedSearchUpdate,
)
from src.services.auth_service import AuthContext

router = APIRouter()


@router.post("/saved-searches", response_model=SavedSearchResponse, status_code=201)
@limiter.limit("30/minute")
async def create_saved_search(
    request: Request,
    body: SavedSearchCreate,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> SavedSearchResponse:
    """Create a new saved search for the caller's organization."""
    org_id = require_org(auth)

    search = SavedSearch(
        org_id=org_id,
        name=body.name,
        criteria=body.criteria.model_dump(exclude_none=True),
        alerts_enabled=body.alerts_enabled,
    )
    db.add(search)
    await db.commit()
    await db.refresh(search)

    return SavedSearchResponse(
        id=search.id,
        org_id=search.org_id,
        name=search.name,
        criteria=search.criteria,
        alerts_enabled=search.alerts_enabled,
        created_at=search.created_at,
        updated_at=search.updated_at,
    )


@router.get("/saved-searches", response_model=list[SavedSearchResponse])
async def list_saved_searches(
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
    page: int = 1,
    per_page: int = 50,
) -> list[SavedSearchResponse]:
    """List saved searches for the caller's organization."""
    org_id = require_org(auth)
    per_page = min(per_page, 100)

    result = await db.execute(
        select(SavedSearch)
        .where(SavedSearch.org_id == org_id)
        .order_by(SavedSearch.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    searches = result.scalars().all()

    return [
        SavedSearchResponse(
            id=s.id,
            org_id=s.org_id,
            name=s.name,
            criteria=s.criteria,
            alerts_enabled=s.alerts_enabled,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in searches
    ]


@router.get("/saved-searches/{search_id}", response_model=SavedSearchResponse)
async def get_saved_search(
    search_id: uuid.UUID,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> SavedSearchResponse:
    """Get a single saved search."""
    org_id = require_org(auth)

    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.org_id == org_id)
    )
    search = result.scalar_one_or_none()
    if not search:
        raise HTTPException(status_code=404, detail="Saved search not found")

    return SavedSearchResponse(
        id=search.id,
        org_id=search.org_id,
        name=search.name,
        criteria=search.criteria,
        alerts_enabled=search.alerts_enabled,
        created_at=search.created_at,
        updated_at=search.updated_at,
    )


@router.put("/saved-searches/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: uuid.UUID,
    body: SavedSearchUpdate,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> SavedSearchResponse:
    """Update a saved search's criteria or alert settings."""
    org_id = require_org(auth)

    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.org_id == org_id)
    )
    search = result.scalar_one_or_none()
    if not search:
        raise HTTPException(status_code=404, detail="Saved search not found")

    if body.name is not None:
        search.name = body.name
    if body.criteria is not None:
        search.criteria = body.criteria.model_dump(exclude_none=True)
    if body.alerts_enabled is not None:
        search.alerts_enabled = body.alerts_enabled

    search.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(search)

    return SavedSearchResponse(
        id=search.id,
        org_id=search.org_id,
        name=search.name,
        criteria=search.criteria,
        alerts_enabled=search.alerts_enabled,
        created_at=search.created_at,
        updated_at=search.updated_at,
    )


@router.delete("/saved-searches/{search_id}", status_code=204)
async def delete_saved_search(
    search_id: uuid.UUID,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> None:
    """Delete a saved search and its alert subscriptions."""
    org_id = require_org(auth)

    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.org_id == org_id)
    )
    search = result.scalar_one_or_none()
    if not search:
        raise HTTPException(status_code=404, detail="Saved search not found")

    await db.delete(search)
    await db.commit()


@router.post(
    "/saved-searches/{search_id}/alerts",
    response_model=AlertSubscriptionResponse,
    status_code=201,
)
@limiter.limit("10/minute")
async def create_alert_subscription(
    request: Request,
    search_id: uuid.UUID,
    body: AlertSubscriptionCreate,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> AlertSubscriptionResponse:
    """Subscribe a webhook endpoint to alerts from a saved search."""
    org_id = require_org(auth)

    # Verify saved search belongs to org
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.org_id == org_id)
    )
    search = result.scalar_one_or_none()
    if not search:
        raise HTTPException(status_code=404, detail="Saved search not found")

    # Verify webhook endpoint belongs to org
    ep_result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == body.webhook_endpoint_id,
            WebhookEndpoint.org_id == org_id,
        )
    )
    if not ep_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    # Enable alerts on the saved search
    search.alerts_enabled = True

    sub = AlertSubscription(
        saved_search_id=search_id,
        webhook_endpoint_id=body.webhook_endpoint_id,
        event_types=body.event_types,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    return AlertSubscriptionResponse(
        id=sub.id,
        saved_search_id=sub.saved_search_id,
        webhook_endpoint_id=sub.webhook_endpoint_id,
        event_types=sub.event_types,
        is_active=sub.is_active,
        created_at=sub.created_at,
    )


@router.get(
    "/saved-searches/{search_id}/alerts",
    response_model=list[AlertSubscriptionResponse],
)
async def list_alert_subscriptions(
    search_id: uuid.UUID,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> list[AlertSubscriptionResponse]:
    """List alert subscriptions for a saved search."""
    org_id = require_org(auth)

    # Verify saved search belongs to org
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.org_id == org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Saved search not found")

    sub_result = await db.execute(
        select(AlertSubscription)
        .where(AlertSubscription.saved_search_id == search_id)
        .order_by(AlertSubscription.created_at.desc())
    )
    subs = sub_result.scalars().all()

    return [
        AlertSubscriptionResponse(
            id=s.id,
            saved_search_id=s.saved_search_id,
            webhook_endpoint_id=s.webhook_endpoint_id,
            event_types=s.event_types,
            is_active=s.is_active,
            created_at=s.created_at,
        )
        for s in subs
    ]


@router.delete("/saved-searches/{search_id}/alerts/{sub_id}", status_code=204)
async def delete_alert_subscription(
    search_id: uuid.UUID,
    sub_id: uuid.UUID,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> None:
    """Delete an alert subscription."""
    org_id = require_org(auth)

    # Verify saved search belongs to org
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.org_id == org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Saved search not found")

    sub_result = await db.execute(
        select(AlertSubscription).where(
            AlertSubscription.id == sub_id,
            AlertSubscription.saved_search_id == search_id,
        )
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Alert subscription not found")

    await db.delete(sub)
    await db.commit()
