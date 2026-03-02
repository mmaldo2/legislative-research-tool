"""Webhook endpoint management and delivery history."""

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session, limiter, require_api_key
from src.models.webhook_delivery import WebhookDelivery
from src.models.webhook_endpoint import WebhookEndpoint
from src.schemas.webhook import (
    WebhookDeliveryResponse,
    WebhookEndpointCreate,
    WebhookEndpointResponse,
    WebhookTestResponse,
)
from src.services.auth_service import AuthContext
from src.services.webhook_dispatcher import enqueue_delivery

router = APIRouter()


def _require_org(auth: AuthContext) -> uuid.UUID:
    if auth.org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    return auth.org_id


@router.post("/webhooks", response_model=WebhookEndpointResponse, status_code=201)
@limiter.limit("10/minute")
async def create_webhook_endpoint(
    request: Request,
    body: WebhookEndpointCreate,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> WebhookEndpointResponse:
    """Register a new webhook endpoint for the caller's organization.

    A signing secret is generated automatically for HMAC-SHA256 verification.
    """
    org_id = _require_org(auth)

    endpoint = WebhookEndpoint(
        org_id=org_id,
        url=str(body.url),
        secret=secrets.token_urlsafe(32),
    )
    db.add(endpoint)
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


@router.get("/webhooks", response_model=list[WebhookEndpointResponse])
async def list_webhook_endpoints(
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> list[WebhookEndpointResponse]:
    """List webhook endpoints for the caller's organization."""
    org_id = _require_org(auth)

    result = await db.execute(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.org_id == org_id)
        .order_by(WebhookEndpoint.created_at.desc())
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


@router.delete("/webhooks/{endpoint_id}", status_code=204)
@limiter.limit("10/minute")
async def delete_webhook_endpoint(
    request: Request,
    endpoint_id: uuid.UUID,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> None:
    """Remove a webhook endpoint and all its delivery history."""
    org_id = _require_org(auth)

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
    org_id = _require_org(auth)

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
    org_id = _require_org(auth)

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
