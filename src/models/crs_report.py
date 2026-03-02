"""Congressional Research Service (CRS) report model."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class CrsReport(Base):
    __tablename__ = "crs_reports"

    id: Mapped[str] = mapped_column(
        String, primary_key=True
    )  # report number e.g. "R12345", "RL33476"
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    authors: Mapped[list | None] = mapped_column(JSONB, default=None)  # list of author names
    topics: Mapped[list | None] = mapped_column(JSONB, default=None)  # list of topic strings
    publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    most_recent_date: Mapped[date | None] = mapped_column(Date, index=True)
    source_url: Mapped[str | None] = mapped_column(String)
    pdf_url: Mapped[str | None] = mapped_column(String)
    related_bill_ids: Mapped[list | None] = mapped_column(
        JSONB, default=None
    )  # internal bill IDs that this report covers
    content_text: Mapped[str | None] = mapped_column(Text)  # plain text extraction if available

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
