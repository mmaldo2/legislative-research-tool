"""Pydantic schemas for research collections."""

from datetime import datetime

from pydantic import BaseModel

from src.schemas.common import MetaResponse


class CollectionCreate(BaseModel):
    name: str
    description: str | None = None


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class CollectionItemAdd(BaseModel):
    bill_id: str
    notes: str | None = None


class CollectionItemUpdate(BaseModel):
    notes: str | None = None


class CollectionItemResponse(BaseModel):
    id: int
    bill_id: str
    notes: str | None = None
    added_at: datetime | None = None


class CollectionResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    item_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CollectionDetailResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    items: list[CollectionItemResponse] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CollectionListResponse(BaseModel):
    data: list[CollectionResponse]
    meta: MetaResponse
