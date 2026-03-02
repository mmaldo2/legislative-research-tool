"""Federal Register regulatory document model."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class RegulatoryDocument(Base):
    __tablename__ = "regulatory_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # FR document number
    document_type: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )  # rule, proposed_rule, notice, presidential_document
    title: Mapped[str] = mapped_column(String, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    agency_names: Mapped[list | None] = mapped_column(JSONB, default=None)
    publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    citation: Mapped[str | None] = mapped_column(String)  # e.g. "89 FR 12345"
    federal_register_url: Mapped[str | None] = mapped_column(String)
    pdf_url: Mapped[str | None] = mapped_column(String)
    topics: Mapped[list | None] = mapped_column(JSONB, default=None)
    cfr_references: Mapped[list | None] = mapped_column(JSONB, default=None)  # CFR parts affected
    related_bill_ids: Mapped[list | None] = mapped_column(
        JSONB, default=None
    )  # internal bill IDs that relate
    raw_text_url: Mapped[str | None] = mapped_column(String)
    docket_ids: Mapped[list | None] = mapped_column(JSONB, default=None)
    regulation_id_numbers: Mapped[list | None] = mapped_column(JSONB, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
