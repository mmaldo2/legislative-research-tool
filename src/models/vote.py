from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class VoteEvent(Base):
    __tablename__ = "vote_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), nullable=False, index=True)
    vote_date: Mapped[date | None] = mapped_column(Date)
    chamber: Mapped[str | None] = mapped_column(String)
    motion_text: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(String)
    yes_count: Mapped[int | None] = mapped_column(Integer)
    no_count: Mapped[int | None] = mapped_column(Integer)
    other_count: Mapped[int | None] = mapped_column(Integer)

    bill: Mapped["Bill"] = relationship(back_populates="vote_events")
    records: Mapped[list["VoteRecord"]] = relationship(back_populates="vote_event")


class VoteRecord(Base):
    __tablename__ = "vote_records"
    __table_args__ = (UniqueConstraint("vote_event_id", "person_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vote_event_id: Mapped[str] = mapped_column(ForeignKey("vote_events.id"), nullable=False)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False)
    option: Mapped[str] = mapped_column(String, nullable=False)

    vote_event: Mapped["VoteEvent"] = relationship(back_populates="records")
    person: Mapped["Person"] = relationship(back_populates="vote_records")
