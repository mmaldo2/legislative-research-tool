"""Pydantic schemas for saved searches and alert subscriptions."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SearchCriteria(BaseModel):
    """Typed search criteria — validated fields only."""

    model_config = {"extra": "forbid"}

    query: str | None = Field(None, max_length=500)
    jurisdiction_id: str | None = Field(None, max_length=50)
    status: str | None = Field(None, max_length=50)


class SavedSearchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    criteria: SearchCriteria
    alerts_enabled: bool = False


class SavedSearchUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    criteria: SearchCriteria | None = None
    alerts_enabled: bool | None = None


class SavedSearchResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    criteria: dict
    alerts_enabled: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AlertSubscriptionCreate(BaseModel):
    webhook_endpoint_id: uuid.UUID
    event_types: list[str] = Field(
        ...,
        min_length=1,
        description="Event types to subscribe to: bill.created, bill.status_changed, etc.",
    )


class AlertSubscriptionResponse(BaseModel):
    id: uuid.UUID
    saved_search_id: uuid.UUID
    webhook_endpoint_id: uuid.UUID
    event_types: list[str]
    is_active: bool
    created_at: datetime | None = None
