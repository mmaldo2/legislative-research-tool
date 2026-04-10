from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_llm_harness, get_session, require_api_key
from src.services.auth_service import AuthContext


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup_overrides(monkeypatch):
    yield
    app.dependency_overrides = {}
    monkeypatch.setattr("src.api.reports.settings.agentic_provider", "", raising=False)
    monkeypatch.setattr("src.api.collections.settings.agentic_provider", "", raising=False)


def _override_session(mock_session):
    async def _gen():
        yield mock_session

    return _gen


def test_reports_generate_uses_codex_adapter_when_enabled(client, monkeypatch):
    mock_session = AsyncMock()
    bill = type("Bill", (), {"jurisdiction_id": "us", "identifier": "S1", "title": "Test", "status": "introduced"})()
    mock_scalars = type("Scalars", (), {"all": lambda self: [bill]})()
    mock_session.execute.return_value = type("Result", (), {"scalars": lambda self: mock_scalars})()

    app.dependency_overrides[get_session] = _override_session(mock_session)
    app.dependency_overrides[get_llm_harness] = lambda: AsyncMock()
    app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

    monkeypatch.setattr("src.api.reports.settings.agentic_provider", "codex-local")
    monkeypatch.setattr("src.api.reports.hybrid_search", AsyncMock(return_value=[("bill-1", 0.9)]))
    monkeypatch.setattr("src.api.reports.extract_bill_text", lambda bill: "Sample text")

    fake_output = {
        "title": "Privacy Memo",
        "executive_summary": "Summary",
        "sections": [{"heading": "Overview", "content": "Body"}],
        "bills_analyzed": 1,
        "jurisdictions_covered": ["us"],
        "key_findings": ["Finding"],
        "trends": [],
        "generated_at": "2026-04-10T00:00:00Z",
        "confidence": 0.8,
    }

    with patch("src.api.reports.generate_report_via_codex", AsyncMock(return_value=type("R", (), {"model_dump": lambda self: fake_output, **fake_output})())) as mock_codex:
        response = client.post("/api/v1/reports/generate", json={"query": "privacy", "max_bills": 5})

    assert response.status_code == 200
    assert response.json()["title"] == "Privacy Memo"
    mock_codex.assert_awaited()


def test_collection_report_uses_codex_adapter_when_enabled(client, monkeypatch):
    mock_session = AsyncMock()
    collection = type("Collection", (), {"id": 1, "name": "Privacy", "items": [type("Item", (), {"bill_id": "bill-1", "notes": None})()]})()
    bill = type("Bill", (), {"id": "bill-1", "jurisdiction_id": "us", "identifier": "S1", "title": "Test", "status": "introduced"})()

    async def fake_get_collection(*args, **kwargs):
        return collection

    mock_scalars = type("Scalars", (), {"all": lambda self: [bill]})()
    mock_session.execute.return_value = type("Result", (), {"scalars": lambda self: mock_scalars})()

    app.dependency_overrides[get_session] = _override_session(mock_session)
    app.dependency_overrides[get_llm_harness] = lambda: AsyncMock()
    app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

    monkeypatch.setattr("src.api.collections.settings.agentic_provider", "codex-local")
    monkeypatch.setattr("src.api.collections._get_collection_or_404", fake_get_collection)
    monkeypatch.setattr("src.api.collections.extract_bill_text", lambda bill: "Sample text")

    fake_output = {
        "title": "Privacy Memo",
        "executive_summary": "Summary",
        "sections": [{"heading": "Overview", "content": "Body"}],
        "bills_analyzed": 1,
        "jurisdictions_covered": ["us"],
        "key_findings": ["Finding"],
        "trends": [],
        "generated_at": "2026-04-10T00:00:00Z",
        "confidence": 0.8,
    }

    with patch("src.api.collections.generate_report_via_codex", AsyncMock(return_value=type("R", (), {"model_dump": lambda self: fake_output, **fake_output})())) as mock_codex:
        response = client.post("/api/v1/collections/1/report")

    assert response.status_code == 200
    assert response.json()["title"] == "Privacy Memo"
    mock_codex.assert_awaited()
