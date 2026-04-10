"""Artifacts saved against research collections/investigations."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class CollectionArtifact(Base):
    __tablename__ = "collection_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String, nullable=False, default="memo")
    title: Mapped[str] = mapped_column(String, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    collection = relationship("Collection")
