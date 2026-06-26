"""Drift Layer 1 (hermetic, always-on): the columns lab/ gold SQL depends on must exist on the
ORM models. Fails CI if a refactor renames/removes a column the harness reads. The test reaches
into src.models (the schema source of truth); lab/ runtime stays standalone."""

from src.models import (
    Bill,
    LegislativeSession,
    Person,
    PersonPartySpan,
    VoteEvent,
    VoteRecord,
)

_MODELS = {
    m.__tablename__: m
    for m in (VoteEvent, VoteRecord, Person, LegislativeSession, Bill, PersonPartySpan)
}


def test_orm_has_required_columns(required_columns):
    for table, cols in required_columns.items():
        actual = set(_MODELS[table].__table__.columns.keys())
        missing = cols - actual
        assert not missing, f"ORM model for {table!r} is missing lab-required columns: {missing}"
