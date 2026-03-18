from datetime import date

from sqlalchemy import ARRAY, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


# NOTE: autoresearch/prepare.py has hardcoded SQL referencing these columns.
# Update that file if you rename or remove columns here.
class BillAction(Base):
    __tablename__ = "bill_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id"), nullable=False, index=True)
    action_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    chamber: Mapped[str | None] = mapped_column(String)
    action_order: Mapped[int | None] = mapped_column(Integer)

    bill: Mapped["Bill"] = relationship(back_populates="actions")
