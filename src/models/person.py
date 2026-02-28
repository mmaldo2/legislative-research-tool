from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Person(Base):
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sort_name: Mapped[str | None] = mapped_column(String)
    party: Mapped[str | None] = mapped_column(String)
    current_jurisdiction_id: Mapped[str | None] = mapped_column(
        ForeignKey("jurisdictions.id")
    )
    current_chamber: Mapped[str | None] = mapped_column(String)
    current_district: Mapped[str | None] = mapped_column(String)
    image_url: Mapped[str | None] = mapped_column(String)

    openstates_id: Mapped[str | None] = mapped_column(String)
    bioguide_id: Mapped[str | None] = mapped_column(String)
    legiscan_id: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )

    sponsorships: Mapped[list["Sponsorship"]] = relationship(back_populates="person")
    vote_records: Mapped[list["VoteRecord"]] = relationship(back_populates="person")
