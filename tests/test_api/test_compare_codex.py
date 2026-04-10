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
    monkeypatch.setattr("src.api.compare.settings.agentic_provider", "", raising=False)


def _override_session(mock_session):
    async def _gen():
        yield mock_session

    return _gen


def test_compare_uses_codex_adapter_when_enabled(client, monkeypatch):
    mock_session = AsyncMock()
    bill_a = type("Bill", (), {"id": "a", "identifier": "A1", "title": "Bill A", "texts": []})()
    bill_b = type("Bill", (), {"id": "b", "identifier": "B1", "title": "Bill B", "texts": []})()

    execute_results = [
        type("Result", (), {"scalar_one_or_none": lambda self: bill_a})(),
        type("Result", (), {"scalar_one_or_none": lambda self: bill_b})(),
    ]

    async def fake_execute(*args, **kwargs):
        return execute_results.pop(0)

    mock_session.execute.side_effect = fake_execute
    mock_session.commit = AsyncMock()

    app.dependency_overrides[get_session] = _override_session(mock_session)
    app.dependency_overrides[get_llm_harness] = lambda: AsyncMock()
    app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

    monkeypatch.setattr("src.api.compare.settings.agentic_provider", "codex-local")
    monkeypatch.setattr("src.api.compare.extract_bill_text", lambda bill: f"Text for {bill.identifier}")

    fake_output = {
        "shared_provisions": ["Shared section"],
        "unique_to_a": ["A only"],
        "unique_to_b": ["B only"],
        "key_differences": ["Different enforcement"],
        "overall_assessment": "Different approaches.",
        "similarity_score": 0.55,
        "is_model_legislation": False,
        "confidence": 0.8,
    }

    with patch("src.api.compare.generate_compare_via_codex", AsyncMock(return_value=type("C", (), {"model_dump": lambda self: fake_output, **fake_output})())) as mock_codex:
        response = client.post("/api/v1/analyze/compare", json={"bill_id_a": "a", "bill_id_b": "b"})

    assert response.status_code == 200
    assert response.json()["similarity_score"] == 0.55
    mock_codex.assert_awaited()
