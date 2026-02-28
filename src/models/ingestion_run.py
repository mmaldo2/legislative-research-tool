from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, nullable=False)  # govinfo, openstates, legiscan
    run_type: Mapped[str] = mapped_column(String, nullable=False)  # full, incremental
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, default="running")  # running, completed, failed
    bills_created: Mapped[int] = mapped_column(Integer, default=0)
    bills_updated: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list | None] = mapped_column(JSONB, default=None)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)
