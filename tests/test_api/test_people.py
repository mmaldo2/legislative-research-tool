"""Tests for people API schemas."""

from src.schemas.common import MetaResponse
from src.schemas.person import PersonListResponse, PersonResponse


class TestPersonResponse:
    def test_full_person(self):
        person = PersonResponse(
            id="ocd-person/abc123",
            name="Jane Smith",
            party="Democratic",
            current_jurisdiction_id="us-ca",
            current_chamber="upper",
            current_district="12",
        )
        assert person.name == "Jane Smith"
        assert person.party == "Democratic"

    def test_minimal_person(self):
        person = PersonResponse(id="abc", name="John Doe")
        assert person.party is None
        assert person.current_chamber is None


class TestPersonListResponse:
    def test_empty_list(self):
        resp = PersonListResponse(
            data=[],
            meta=MetaResponse(total_count=0, page=1, per_page=20),
        )
        assert resp.data == []
        assert resp.meta.total_count == 0

    def test_with_people(self):
        resp = PersonListResponse(
            data=[
                PersonResponse(id="a", name="Alice"),
                PersonResponse(id="b", name="Bob"),
            ],
            meta=MetaResponse(total_count=2, page=1, per_page=20),
        )
        assert len(resp.data) == 2
