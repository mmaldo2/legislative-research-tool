"""Vote-time party spans — a member's party affiliation over a date range.

Populated from unitedstates/congress-legislators (per-term `party` + `party_affiliations`) by
`src/ingestion/congress_legislators.py::ingest_term_history()`. The Condorcet Lab Family 1
party-keyed templates (Phase 3b/3c — party_breakdown / party_defection / crossed_party) resolve a
voter's party AS OF a roll-call's `vote_date` via this table; they MUST NOT read `people.party`
(a single *current* value that post-dates party-switchers). Voter-scoped (only bioguides present in
`people`) — NOT a complete member registry.

`end_date` is an EXCLUSIVE upper bound: resolve with `start_date <= vote_date < end_date`
(half-open, so adjacent spans that share a boundary day never double-resolve).
"""

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class PersonPartySpan(Base):
    __tablename__ = "person_party_spans"
    __table_args__ = (
        # Natural key + integrity guard: a member can't have two spans starting the same day.
        # Also indexes person_id as its leading column (no separate index needed for the
        # as-of-date join's `person_id =` filter).
        UniqueConstraint("person_id", "start_date", name="uq_person_party_spans_person_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[str] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    party: Mapped[str] = mapped_column(String, nullable=False)  # D | R | I | L
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)  # EXCLUSIVE upper bound
