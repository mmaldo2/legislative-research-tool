"""Bill change event model — tracks per-field changes detected during ingestion."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class BillChangeEvent(Base):
    __tablename__ = "bill_change_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("bills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # created, updated, status_changed, text_added, action_added
    field_name: Mapped[str | None] = mapped_column(String)
    old_value: Mapped[str | None] = mapped_column(String)
    new_value: Mapped[str | None] = mapped_column(String)
    ingestion_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ingestion_runs.id", ondelete="SET NULL"),
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
