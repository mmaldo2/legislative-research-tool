"""Tests for new API endpoint schemas — votes, jurisdictions, sessions, analyses."""

from datetime import date, datetime
from decimal import Decimal

from src.schemas.analysis import AnalysisListResponse, AnalysisResponse
from src.schemas.common import MetaResponse
from src.schemas.jurisdiction import JurisdictionListResponse, JurisdictionResponse
from src.schemas.session import SessionListResponse, SessionResponse
from src.schemas.vote import VoteEventListResponse, VoteEventResponse, VoteRecordResponse


class TestVoteSchemas:
    def test_vote_record(self):
        record = VoteRecordResponse(person_id="p1", person_name="Jane Smith", option="yes")
        assert record.option == "yes"
        assert record.person_name == "Jane Smith"

    def test_vote_event(self):
        event = VoteEventResponse(
            id="vote-1",
            bill_id="bill-1",
            vote_date=date(2025, 3, 15),
            chamber="upper",
            motion_text="Passage of the bill",
            result="pass",
            yes_count=55,
            no_count=40,
            other_count=5,
            records=[
                VoteRecordResponse(person_id="p1", option="yes"),
                VoteRecordResponse(person_id="p2", option="no"),
            ],
        )
        assert event.result == "pass"
        assert len(event.records) == 2

    def test_vote_event_minimal(self):
        event = VoteEventResponse(id="v1", bill_id="b1")
        assert event.vote_date is None
        assert event.records == []

    def test_vote_event_list_response(self):
        resp = VoteEventListResponse(
            data=[VoteEventResponse(id="v1", bill_id="b1", result="pass")],
            meta=MetaResponse(total_count=1, page=1, per_page=20),
        )
        assert len(resp.data) == 1


class TestJurisdictionSchemas:
    def test_full_jurisdiction(self):
        j = JurisdictionResponse(
            id="us-ca",
            name="California",
            classification="state",
            abbreviation="CA",
            fips_code="06",
        )
        assert j.abbreviation == "CA"

    def test_minimal_jurisdiction(self):
        j = JurisdictionResponse(id="us", name="United States", classification="country")
        assert j.abbreviation is None

    def test_jurisdiction_list(self):
        resp = JurisdictionListResponse(
            data=[
                JurisdictionResponse(id="us", name="United States", classification="country"),
                JurisdictionResponse(id="us-ca", name="California", classification="state"),
            ],
            meta=MetaResponse(total_count=2, page=1, per_page=50),
        )
        assert len(resp.data) == 2
        assert resp.meta.total_count == 2


class TestSessionSchemas:
    def test_full_session(self):
        s = SessionResponse(
            id="us-119",
            jurisdiction_id="us",
            name="119th Congress",
            identifier="119",
            classification="primary",
            start_date=date(2025, 1, 3),
            end_date=date(2027, 1, 3),
        )
        assert s.start_date == date(2025, 1, 3)

    def test_minimal_session(self):
        s = SessionResponse(
            id="us-ca-2025",
            jurisdiction_id="us-ca",
            name="2025 Regular Session",
            identifier="2025",
        )
        assert s.classification is None
        assert s.start_date is None

    def test_session_list(self):
        resp = SessionListResponse(
            data=[],
            meta=MetaResponse(total_count=0, page=1, per_page=50),
        )
        assert resp.data == []


class TestAnalysisListSchemas:
    def test_analysis_response(self):
        a = AnalysisResponse(
            id=1,
            bill_id="bill-1",
            analysis_type="summary",
            result={"plain_english_summary": "Test summary"},
            model_used="claude-sonnet-4-6",
            prompt_version="v1",
            confidence=Decimal("0.95"),
            tokens_input=1000,
            tokens_output=200,
            cost_usd=Decimal("0.005"),
            created_at=datetime(2025, 6, 1),
        )
        assert a.model_used == "claude-sonnet-4-6"
        assert a.confidence == Decimal("0.95")

    def test_analysis_minimal(self):
        a = AnalysisResponse(
            id=2,
            bill_id="bill-2",
            analysis_type="classification",
            result={"primary_topic": "Health"},
            model_used="claude-haiku-4-5",
            prompt_version="v1",
        )
        assert a.confidence is None
        assert a.tokens_input is None

    def test_analysis_list(self):
        resp = AnalysisListResponse(
            data=[
                AnalysisResponse(
                    id=1,
                    bill_id="b1",
                    analysis_type="summary",
                    result={},
                    model_used="claude-sonnet-4-6",
                    prompt_version="v1",
                ),
            ],
            meta=MetaResponse(total_count=1, page=1, per_page=20, ai_enriched=True),
        )
        assert resp.meta.ai_enriched is True
        assert len(resp.data) == 1
