"""Committee hearing models for tracking congressional hearings."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class CommitteeHearing(Base):
    __tablename__ = "committee_hearings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bill_id: Mapped[str | None] = mapped_column(ForeignKey("bills.id"), nullable=True, index=True)
    committee_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    committee_code: Mapped[str | None] = mapped_column(String)
    chamber: Mapped[str | None] = mapped_column(String, index=True)  # senate, house, joint
    title: Mapped[str] = mapped_column(String, nullable=False)
    hearing_date: Mapped[date | None] = mapped_column(Date, index=True)
    location: Mapped[str | None] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(String)
    congress: Mapped[int | None] = mapped_column(Integer)
    jacket_number: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

    # Many-to-many link to bills
    bill_links: Mapped[list["HearingBillLink"]] = relationship(
        back_populates="hearing", cascade="all, delete-orphan"
    )


class HearingBillLink(Base):
    __tablename__ = "hearing_bill_links"

    hearing_id: Mapped[str] = mapped_column(
        ForeignKey("committee_hearings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    bill_id: Mapped[str] = mapped_column(
        ForeignKey("bills.id", ondelete="CASCADE"),
        primary_key=True,
    )

    hearing: Mapped["CommitteeHearing"] = relationship(back_populates="bill_links")
