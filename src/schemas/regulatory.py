"""Pydantic response schemas for Federal Register regulatory documents."""

from datetime import date, datetime

from pydantic import BaseModel

from src.schemas.common import MetaResponse


class RegulatoryDocumentResponse(BaseModel):
    id: str
    document_type: str
    title: str
    abstract: str | None = None
    agency_names: list[str] | None = None
    publication_date: date | None = None
    citation: str | None = None
    federal_register_url: str | None = None
    pdf_url: str | None = None
    topics: list[str] | None = None
    cfr_references: list[dict] | None = None
    related_bill_ids: list[str] | None = None
    docket_ids: list[str] | None = None
    regulation_id_numbers: list[str] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RegulatoryDocumentListResponse(BaseModel):
    data: list[RegulatoryDocumentResponse]
    meta: MetaResponse
