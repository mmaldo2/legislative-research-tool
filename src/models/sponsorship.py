from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Sponsorship(Base):
    __tablename__ = "sponsorships"
    __table_args__ = (
        UniqueConstraint("bill_id", "person_id", "classification"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), nullable=False, index=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    classification: Mapped[str] = mapped_column(String, nullable=False)

    bill: Mapped["Bill"] = relationship(back_populates="sponsorships")
    person: Mapped["Person"] = relationship(back_populates="sponsorships")
