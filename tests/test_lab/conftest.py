"""Shared fixtures for the lab tests."""

import pytest

# The exact set of columns the lab/ gold SQL depends on, per gold table. This manifest is the
# canonical statement of lab's schema surface; the drift tests assert it against both the ORM
# (hermetic) and the live DB (requires_pg).
REQUIRED_COLUMNS = {
    "vote_events": {
        "id",
        "bill_id",
        "vote_date",
        "chamber",
        "motion_text",
        "result",
        "yes_count",
        "no_count",
        "other_count",
    },
    "vote_records": {"id", "vote_event_id", "person_id", "option"},
    "people": {"id", "name", "party"},
    "sessions": {"id", "identifier", "end_date"},
    "bills": {"id", "identifier", "session_id"},
    "person_party_spans": {"id", "person_id", "party", "start_date", "end_date"},
}


@pytest.fixture
def required_columns():
    return REQUIRED_COLUMNS
