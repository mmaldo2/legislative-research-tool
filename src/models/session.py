from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class LegislativeSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    jurisdiction_id: Mapped[str] = mapped_column(ForeignKey("jurisdictions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    identifier: Mapped[str] = mapped_column(String, nullable=False)
    classification: Mapped[str | None] = mapped_column(String)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)

    jurisdiction: Mapped["Jurisdiction"] = relationship(back_populates="sessions")
    bills: Mapped[list["Bill"]] = relationship(back_populates="session")
