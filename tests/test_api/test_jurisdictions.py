"""Tests for jurisdiction API schemas."""

from src.schemas.jurisdiction import (
    JurisdictionStatsResponse,
    SessionBillCount,
    SubjectCount,
)


class TestJurisdictionStatsResponse:
    def test_full_stats(self):
        stats = JurisdictionStatsResponse(
            total_bills=500,
            total_legislators=120,
            bills_by_status={"introduced": 300, "enacted": 50, "vetoed": 10, "failed": 140},
            bills_by_session=[
                SessionBillCount(
                    session_id="us-ca-2025", session_name="2025 Regular Session", bill_count=250
                ),
                SessionBillCount(
                    session_id="us-ca-2024", session_name="2024 Regular Session", bill_count=250
                ),
            ],
            top_subjects=[
                SubjectCount(subject="Education", count=45),
                SubjectCount(subject="Healthcare", count=38),
            ],
        )
        assert stats.total_bills == 500
        assert stats.total_legislators == 120
        assert stats.bills_by_status["enacted"] == 50
        assert len(stats.bills_by_session) == 2
        assert stats.bills_by_session[0].bill_count == 250
        assert len(stats.top_subjects) == 2
        assert stats.top_subjects[0].subject == "Education"

    def test_empty_stats(self):
        stats = JurisdictionStatsResponse(
            total_bills=0,
            total_legislators=0,
            bills_by_status={},
            bills_by_session=[],
            top_subjects=[],
        )
        assert stats.total_bills == 0
        assert stats.bills_by_status == {}
        assert stats.bills_by_session == []
        assert stats.top_subjects == []

    def test_serialization_roundtrip(self):
        stats = JurisdictionStatsResponse(
            total_bills=100,
            total_legislators=40,
            bills_by_status={"introduced": 80, "enacted": 20},
            bills_by_session=[
                SessionBillCount(
                    session_id="us-119", session_name="119th Congress", bill_count=100
                ),
            ],
            top_subjects=[
                SubjectCount(subject="Privacy", count=15),
            ],
        )
        data = stats.model_dump()
        rebuilt = JurisdictionStatsResponse(**data)
        assert rebuilt == stats


class TestSessionBillCount:
    def test_valid(self):
        sbc = SessionBillCount(
            session_id="us-119", session_name="119th Congress", bill_count=1500
        )
        assert sbc.session_id == "us-119"
        assert sbc.bill_count == 1500


class TestSubjectCount:
    def test_valid(self):
        sc = SubjectCount(subject="Criminal Justice", count=42)
        assert sc.subject == "Criminal Justice"
        assert sc.count == 42
