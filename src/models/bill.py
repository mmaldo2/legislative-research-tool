from datetime import date, datetime

from sqlalchemy import ARRAY, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (UniqueConstraint("jurisdiction_id", "session_id", "identifier"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    jurisdiction_id: Mapped[str] = mapped_column(
        ForeignKey("jurisdictions.id"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    identifier: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    classification: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    subject: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    status: Mapped[str | None] = mapped_column(String, index=True)
    status_date: Mapped[date | None] = mapped_column(Date)

    openstates_id: Mapped[str | None] = mapped_column(String)
    legiscan_id: Mapped[int | None] = mapped_column()
    congress_bill_id: Mapped[str | None] = mapped_column(String)
    govinfo_package_id: Mapped[str | None] = mapped_column(String)

    source_urls: Mapped[list[str] | None] = mapped_column(JSONB, default=None)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

    jurisdiction: Mapped["Jurisdiction"] = relationship(back_populates="bills")
    session: Mapped["LegislativeSession"] = relationship(back_populates="bills")
    texts: Mapped[list["BillText"]] = relationship(back_populates="bill")
    actions: Mapped[list["BillAction"]] = relationship(back_populates="bill")
    sponsorships: Mapped[list["Sponsorship"]] = relationship(back_populates="bill")
    vote_events: Mapped[list["VoteEvent"]] = relationship(back_populates="bill")
    analyses: Mapped[list["AiAnalysis"]] = relationship(back_populates="bill")
