"""Tests for people API schemas."""

from datetime import date

from src.schemas.common import MetaResponse
from src.schemas.person import (
    PersonListResponse,
    PersonResponse,
    PersonStatsResponse,
    PersonVoteListResponse,
    PersonVoteResponse,
)


class TestPersonResponse:
    def test_full_person(self):
        person = PersonResponse(
            id="ocd-person/abc123",
            name="Jane Smith",
            party="Democratic",
            current_jurisdiction_id="us-ca",
            current_chamber="upper",
            current_district="12",
            image_url="https://example.com/photo.jpg",
        )
        assert person.name == "Jane Smith"
        assert person.party == "Democratic"
        assert person.image_url == "https://example.com/photo.jpg"

    def test_minimal_person(self):
        person = PersonResponse(id="abc", name="John Doe")
        assert person.party is None
        assert person.current_chamber is None
        assert person.image_url is None

    def test_image_url_optional(self):
        person = PersonResponse(id="abc", name="John Doe", image_url=None)
        assert person.image_url is None


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


class TestPersonVoteResponse:
    def test_full_vote(self):
        vote = PersonVoteResponse(
            vote_event_id="vote-001",
            bill_id="bill-abc",
            bill_identifier="HR 1234",
            bill_title="Consumer Privacy Act",
            vote_date=date(2025, 6, 15),
            chamber="lower",
            motion_text="On Passage",
            result="pass",
            option="yes",
        )
        assert vote.option == "yes"
        assert vote.bill_identifier == "HR 1234"
        assert vote.result == "pass"

    def test_minimal_vote(self):
        vote = PersonVoteResponse(
            vote_event_id="vote-001",
            bill_id="bill-abc",
            bill_identifier="HR 1234",
            bill_title="Test Bill",
            option="no",
        )
        assert vote.vote_date is None
        assert vote.chamber is None
        assert vote.motion_text is None
        assert vote.result is None

    def test_various_options(self):
        for opt in ["yes", "no", "not voting", "excused", "present"]:
            vote = PersonVoteResponse(
                vote_event_id="v1",
                bill_id="b1",
                bill_identifier="S 1",
                bill_title="Test",
                option=opt,
            )
            assert vote.option == opt


class TestPersonVoteListResponse:
    def test_empty_list(self):
        resp = PersonVoteListResponse(
            data=[],
            meta=MetaResponse(total_count=0, page=1, per_page=20),
        )
        assert resp.data == []
        assert resp.meta.total_count == 0

    def test_with_votes(self):
        votes = [
            PersonVoteResponse(
                vote_event_id=f"v{i}",
                bill_id=f"b{i}",
                bill_identifier=f"HR {i}",
                bill_title=f"Bill {i}",
                option="yes" if i % 2 == 0 else "no",
            )
            for i in range(3)
        ]
        resp = PersonVoteListResponse(
            data=votes,
            meta=MetaResponse(total_count=3, page=1, per_page=20),
        )
        assert len(resp.data) == 3


class TestPersonStatsResponse:
    def test_full_stats(self):
        stats = PersonStatsResponse(
            bills_sponsored=15,
            bills_cosponsored=42,
            votes_cast=200,
            vote_participation_rate=0.85,
        )
        assert stats.bills_sponsored == 15
        assert stats.bills_cosponsored == 42
        assert stats.votes_cast == 200
        assert stats.vote_participation_rate == 0.85

    def test_zero_stats(self):
        stats = PersonStatsResponse(
            bills_sponsored=0,
            bills_cosponsored=0,
            votes_cast=0,
        )
        assert stats.bills_sponsored == 0
        assert stats.vote_participation_rate is None

    def test_participation_rate_optional(self):
        stats = PersonStatsResponse(
            bills_sponsored=5,
            bills_cosponsored=10,
            votes_cast=0,
            vote_participation_rate=None,
        )
        assert stats.vote_participation_rate is None

    def test_serialization_roundtrip(self):
        stats = PersonStatsResponse(
            bills_sponsored=5,
            bills_cosponsored=10,
            votes_cast=50,
            vote_participation_rate=0.7523,
        )
        data = stats.model_dump()
        rebuilt = PersonStatsResponse(**data)
        assert rebuilt == stats
