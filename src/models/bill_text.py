from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class BillText(Base):
    __tablename__ = "bill_texts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), nullable=False, index=True)
    version_name: Mapped[str] = mapped_column(String, nullable=False)
    version_date: Mapped[date | None] = mapped_column(Date)
    content_text: Mapped[str | None] = mapped_column(Text)
    content_html: Mapped[str | None] = mapped_column(Text)
    content_xml: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String)
    word_count: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )

    bill: Mapped["Bill"] = relationship(back_populates="texts")
