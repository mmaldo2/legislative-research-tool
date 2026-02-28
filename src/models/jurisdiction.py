from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Jurisdiction(Base):
    __tablename__ = "jurisdictions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    classification: Mapped[str] = mapped_column(String, nullable=False)
    abbreviation: Mapped[str | None] = mapped_column(String)
    fips_code: Mapped[str | None] = mapped_column(String)

    sessions: Mapped[list["LegislativeSession"]] = relationship(back_populates="jurisdiction")
    bills: Mapped[list["Bill"]] = relationship(back_populates="jurisdiction")
