from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class BillSimilarity(Base):
    __tablename__ = "bill_similarities"
    __table_args__ = (CheckConstraint("bill_id_a < bill_id_b", name="canonical_ordering"),)

    bill_id_a: Mapped[str] = mapped_column(ForeignKey("bills.id"), primary_key=True)
    bill_id_b: Mapped[str] = mapped_column(ForeignKey("bills.id"), primary_key=True)
    similarity_type: Mapped[str] = mapped_column(String, primary_key=True)  # semantic, text_overlap
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
