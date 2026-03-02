"""Pydantic schemas for webhook endpoints and deliveries."""

import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class WebhookEndpointCreate(BaseModel):
    url: HttpUrl


class WebhookEndpointResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    url: str
    is_active: bool
    failure_count: int
    created_at: datetime | None = None


class WebhookEndpointCreateResponse(WebhookEndpointResponse):
    """Returned only on POST — includes the signing secret (shown once)."""

    secret: str


class WebhookDeliveryResponse(BaseModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str
    idempotency_key: str
    status: str
    attempt_count: int
    last_status_code: int | None = None
    last_error: str | None = None
    next_retry_at: datetime | None = None
    created_at: datetime | None = None
    delivered_at: datetime | None = None


class WebhookTestResponse(BaseModel):
    delivery_id: uuid.UUID
    status: str
    message: str
