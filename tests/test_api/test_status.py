"""Tests for health and status API schemas."""

from datetime import datetime

from src.api.status import HealthResponse, IngestionRunResponse, StatusResponse


class TestHealthResponse:
    def test_healthy(self):
        resp = HealthResponse(status="ok", version="0.1.0", database="connected")
        assert resp.status == "ok"
        assert resp.version == "0.1.0"
        assert resp.database == "connected"

    def test_unhealthy_db(self):
        resp = HealthResponse(status="ok", version="0.1.0", database="disconnected")
        assert resp.database == "disconnected"


class TestIngestionRunResponse:
    def test_completed_run(self):
        run = IngestionRunResponse(
            id=1,
            source="govinfo",
            run_type="full",
            status="completed",
            started_at=datetime(2025, 1, 1),
            finished_at=datetime(2025, 1, 1, 0, 30),
            bills_created=500,
            bills_updated=50,
        )
        assert run.source == "govinfo"
        assert run.bills_created == 500

    def test_running_run(self):
        run = IngestionRunResponse(
            id=2,
            source="openstates",
            run_type="incremental",
            status="running",
            bills_created=0,
            bills_updated=0,
        )
        assert run.finished_at is None


class TestStatusResponse:
    def test_status_summary(self):
        status = StatusResponse(
            total_bills=10000,
            total_jurisdictions=52,
            recent_runs=[],
        )
        assert status.total_bills == 10000
        assert status.total_jurisdictions == 52
        assert status.recent_runs == []
