from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class BillEmbedding(Base):
    __tablename__ = "bill_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), nullable=False, index=True)
    text_id: Mapped[str | None] = mapped_column(ForeignKey("bill_texts.id"))
    # vector column added via raw SQL migration (pgvector type not in SQLAlchemy core)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
