"""Webhook endpoint management and delivery history."""

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session, limiter, require_api_key, require_org
from src.models.webhook_delivery import WebhookDelivery
from src.models.webhook_endpoint import WebhookEndpoint
from src.schemas.webhook import (
    WebhookDeliveryResponse,
    WebhookEndpointCreate,
    WebhookEndpointCreateResponse,
    WebhookEndpointResponse,
    WebhookEndpointUpdate,
    WebhookTestResponse,
)
from src.services.auth_service import AuthContext
from src.services.webhook_dispatcher import enqueue_delivery, validate_webhook_url

router = APIRouter()


@router.post("/webhooks", response_model=WebhookEndpointCreateResponse, status_code=201)
@limiter.limit("10/minute")
async def create_webhook_endpoint(
    request: Request,
    body: WebhookEndpointCreate,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> WebhookEndpointCreateResponse:
    """Register a new webhook endpoint for the caller's organization.

    A signing secret is generated automatically for HMAC-SHA256 verification.
    The secret is returned only in this response — store it securely.
    """
    org_id = require_org(auth)

    url = str(body.url)
    ssrf_error = validate_webhook_url(url)
    if ssrf_error:
        raise HTTPException(status_code=422, detail=ssrf_error)

    endpoint = WebhookEndpoint(
        org_id=org_id,
        url=url,
        secret=secrets.token_urlsafe(32),
    )
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)

    return WebhookEndpointCreateResponse(
        id=endpoint.id,
        org_id=endpoint.org_id,
        url=endpoint.url,
        is_active=endpoint.is_active,
        failure_count=endpoint.failure_count,
        created_at=endpoint.created_at,
        secret=endpoint.secret,
    )


@router.get("/webhooks", response_model=list[WebhookEndpointResponse])
async def list_webhook_endpoints(
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
    page: int = 1,
    per_page: int = 50,
) -> list[WebhookEndpointResponse]:
    """List webhook endpoints for the caller's organization."""
    org_id = require_org(auth)
    per_page = min(per_page, 100)

    result = await db.execute(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.org_id == org_id)
        .order_by(WebhookEndpoint.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    endpoints = result.scalars().all()

    return [
        WebhookEndpointResponse(
            id=ep.id,
            org_id=ep.org_id,
            url=ep.url,
            is_active=ep.is_active,
            failure_count=ep.failure_count,
            created_at=ep.created_at,
        )
        for ep in endpoints
    ]


@router.get("/webhooks/{endpoint_id}", response_model=WebhookEndpointResponse)
async def get_webhook_endpoint(
    endpoint_id: uuid.UUID,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> WebhookEndpointResponse:
    """Get a single webhook endpoint."""
    org_id = require_org(auth)

    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.org_id == org_id,
        )
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    return WebhookEndpointResponse(
        id=endpoint.id,
        org_id=endpoint.org_id,
        url=endpoint.url,
        is_active=endpoint.is_active,
        failure_count=endpoint.failure_count,
        created_at=endpoint.created_at,
    )


@router.patch("/webhooks/{endpoint_id}", response_model=WebhookEndpointResponse)
async def update_webhook_endpoint(
    endpoint_id: uuid.UUID,
    body: WebhookEndpointUpdate,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> WebhookEndpointResponse:
    """Update a webhook endpoint (e.g. reactivate after circuit breaker)."""
    org_id = require_org(auth)

    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.org_id == org_id,
        )
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    if body.is_active is not None:
        endpoint.is_active = body.is_active
        if body.is_active:
            endpoint.failure_count = 0

    await db.commit()
    await db.refresh(endpoint)

    return WebhookEndpointResponse(
        id=endpoint.id,
        org_id=endpoint.org_id,
        url=endpoint.url,
        is_active=endpoint.is_active,
        failure_count=endpoint.failure_count,
        created_at=endpoint.created_at,
    )


@router.delete("/webhooks/{endpoint_id}", status_code=204)
@limiter.limit("10/minute")
async def delete_webhook_endpoint(
    request: Request,
    endpoint_id: uuid.UUID,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> None:
    """Remove a webhook endpoint and all its delivery history."""
    org_id = require_org(auth)

    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.org_id == org_id,
        )
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    await db.delete(endpoint)
    await db.commit()


@router.get(
    "/webhooks/{endpoint_id}/deliveries",
    response_model=list[WebhookDeliveryResponse],
)
async def list_deliveries(
    endpoint_id: uuid.UUID,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
    limit: int = 50,
) -> list[WebhookDeliveryResponse]:
    """List delivery history for a webhook endpoint."""
    org_id = require_org(auth)

    # Verify endpoint belongs to org
    ep_result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.org_id == org_id,
        )
    )
    if not ep_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    result = await db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.endpoint_id == endpoint_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(min(limit, 200))
    )
    deliveries = result.scalars().all()

    return [
        WebhookDeliveryResponse(
            id=d.id,
            endpoint_id=d.endpoint_id,
            event_type=d.event_type,
            idempotency_key=d.idempotency_key,
            status=d.status,
            attempt_count=d.attempt_count,
            last_status_code=d.last_status_code,
            last_error=d.last_error,
            next_retry_at=d.next_retry_at,
            created_at=d.created_at,
            delivered_at=d.delivered_at,
        )
        for d in deliveries
    ]


@router.post(
    "/webhooks/{endpoint_id}/test",
    response_model=WebhookTestResponse,
    status_code=201,
)
@limiter.limit("5/minute")
async def test_webhook(
    request: Request,
    endpoint_id: uuid.UUID,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> WebhookTestResponse:
    """Send a test payload to a webhook endpoint."""
    org_id = require_org(auth)

    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.org_id == org_id,
        )
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    test_payload = {
        "event_type": "webhook.test",
        "message": "This is a test webhook delivery",
        "endpoint_id": str(endpoint_id),
    }

    delivery = await enqueue_delivery(db, endpoint, "webhook.test", test_payload)
    await db.commit()
    await db.refresh(delivery)

    return WebhookTestResponse(
        delivery_id=delivery.id,
        status=delivery.status,
        message="Test webhook delivery enqueued",
    )
