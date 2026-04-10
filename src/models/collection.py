"""Research collection models — user-curated groups of bills."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["CollectionItem"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )


class CollectionItem(Base):
    __tablename__ = "collection_items"
    __table_args__ = (UniqueConstraint("collection_id", "bill_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    collection: Mapped["Collection"] = relationship(back_populates="items")
    bill: Mapped["Bill"] = relationship()
