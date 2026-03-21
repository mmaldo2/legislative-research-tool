"""Tests for policy workspace composer endpoints."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_llm_harness, get_session, require_api_key
from src.services.auth_service import AuthContext
from src.services.policy_composer_service import OutlineGenerationError


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides = {}


def _override_session(mock_session):
    async def _gen():
        yield mock_session

    return _gen


def _mock_workspace(**overrides):
    defaults = {
        "id": "workspace123",
        "title": "Privacy Model Act",
        "target_jurisdiction_id": "us-ca",
        "drafting_template": "general-model-act",
        "goal_prompt": "Modernize state privacy protections.",
        "status": "setup",
        "created_at": datetime(2026, 3, 20),
        "updated_at": datetime(2026, 3, 20),
        "precedents": [],
        "sections": [],
        "generations": [],
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _mock_precedent(**overrides):
    bill = SimpleNamespace(
        id="bill-1",
        identifier="AB 101",
        title="Privacy Baseline Act",
        jurisdiction_id="us-ca",
        status="introduced",
    )
    defaults = {
        "id": 1,
        "bill_id": "bill-1",
        "position": 0,
        "added_at": datetime(2026, 3, 20),
        "bill": bill,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _mock_section(**overrides):
    defaults = {
        "id": "section-1",
        "section_key": "definitions",
        "heading": "Definitions",
        "purpose": "Define key terms and scope for the model act.",
        "position": 0,
        "content_markdown": "",
        "status": "outlined",
        "created_at": datetime(2026, 3, 20),
        "updated_at": datetime(2026, 3, 20),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _mock_generation(**overrides):
    defaults = {
        "id": "generation-1",
        "action_type": "outline",
        "created_at": datetime(2026, 3, 20),
        "output_payload": {
            "sections": [
                {
                    "section_key": "definitions",
                    "heading": "Definitions",
                    "purpose": "Define key terms and scope for the model act.",
                    "sources": [
                        {
                            "bill_id": "bill-1",
                            "identifier": "AB 101",
                            "title": "Privacy Baseline Act",
                            "jurisdiction_id": "us-ca",
                            "note": "Use the definition set as a starting point.",
                        }
                    ],
                }
            ],
            "drafting_notes": ["Tighten private right of action language for the target state."],
            "confidence": 0.84,
        },
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestPolicyWorkspaceEndpoints:
    def test_create_returns_201(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        with patch(
            "src.api.policy_workspaces.create_workspace",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = _mock_workspace()
            response = client.post(
                "/api/v1/policy-workspaces",
                headers={"X-Client-Id": "client-1"},
                json={
                    "title": "Privacy Model Act",
                    "target_jurisdiction_id": "us-ca",
                    "drafting_template": "general-model-act",
                    "goal_prompt": "Modernize state privacy protections.",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "workspace123"
        assert data["target_jurisdiction_id"] == "us-ca"
        assert data["drafting_template"] == "general-model-act"

    def test_list_returns_data_and_meta(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        workspace = _mock_workspace(status="drafting")
        rows = [(workspace, 2, 1)]

        with patch(
            "src.api.policy_workspaces.list_workspaces",
            new_callable=AsyncMock,
        ) as mock_list:
            mock_list.return_value = (rows, 1)
            response = client.get(
                "/api/v1/policy-workspaces",
                headers={"X-Client-Id": "client-1"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["total_count"] == 1
        assert data["data"][0]["precedent_count"] == 2
        assert data["data"][0]["section_count"] == 1

    def test_get_detail_returns_nested_precedents(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        precedent = _mock_precedent()
        workspace = _mock_workspace(precedents=[precedent])

        with patch(
            "src.api.policy_workspaces.get_workspace_detail",
            new_callable=AsyncMock,
        ) as mock_detail:
            mock_detail.return_value = workspace
            response = client.get(
                "/api/v1/policy-workspaces/workspace123",
                headers={"X-Client-Id": "client-1"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["precedents"][0]["identifier"] == "AB 101"
        assert data["precedents"][0]["title"] == "Privacy Baseline Act"

    def test_generate_outline_returns_sections_with_provenance(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")
        app.dependency_overrides[get_llm_harness] = lambda: AsyncMock()

        workspace = _mock_workspace(
            status="outline_ready",
            sections=[_mock_section()],
            generations=[_mock_generation()],
        )

        with patch(
            "src.api.policy_workspaces.generate_outline_for_workspace",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.return_value = workspace
            response = client.post(
                "/api/v1/policy-workspaces/workspace123/outline/generate",
                headers={"X-Client-Id": "client-1"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "outline_ready"
        assert data["sections"][0]["heading"] == "Definitions"
        assert data["sections"][0]["provenance"][0]["identifier"] == "AB 101"
        assert data["outline_drafting_notes"][0].startswith("Tighten private right of action")

    def test_generate_outline_validation_failure_returns_502(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")
        app.dependency_overrides[get_llm_harness] = lambda: AsyncMock()

        with patch(
            "src.api.policy_workspaces.generate_outline_for_workspace",
            new_callable=AsyncMock,
        ) as mock_generate:
            mock_generate.side_effect = OutlineGenerationError(
                "Outline generation returned no sections"
            )
            response = client.post(
                "/api/v1/policy-workspaces/workspace123/outline/generate",
                headers={"X-Client-Id": "client-1"},
            )

        assert response.status_code == 502
        assert response.json()["detail"] == "Outline generation returned no sections"

    def test_get_detail_prefers_latest_outline_generation(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        older_generation = _mock_generation(
            created_at=datetime(2026, 3, 19),
            output_payload={
                "sections": [
                    {
                        "section_key": "definitions",
                        "heading": "Definitions",
                        "purpose": "Legacy definition section.",
                        "sources": [],
                    }
                ],
                "drafting_notes": ["Older note"],
                "confidence": 0.4,
            },
        )
        newer_generation = _mock_generation(created_at=datetime(2026, 3, 20, 12, 0, 0))
        workspace = _mock_workspace(
            sections=[_mock_section()],
            generations=[newer_generation, older_generation],
        )

        with patch(
            "src.api.policy_workspaces.get_workspace_detail",
            new_callable=AsyncMock,
        ) as mock_detail:
            mock_detail.return_value = workspace
            response = client.get(
                "/api/v1/policy-workspaces/workspace123",
                headers={"X-Client-Id": "client-1"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["outline_confidence"] == pytest.approx(0.84)
        assert data["outline_drafting_notes"] == [
            "Tighten private right of action language for the target state."
        ]
        assert data["sections"][0]["provenance"][0]["identifier"] == "AB 101"

    def test_update_section_returns_200(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        workspace = _mock_workspace(
            sections=[
                _mock_section(
                    status="edited",
                    purpose="Refined scope and term definitions.",
                )
            ],
            generations=[_mock_generation()],
        )

        with patch(
            "src.api.policy_workspaces.update_workspace_section",
            new_callable=AsyncMock,
        ) as mock_update:
            mock_update.return_value = workspace
            response = client.patch(
                "/api/v1/policy-workspaces/workspace123/sections/section-1",
                headers={"X-Client-Id": "client-1"},
                json={"heading": "Definitions", "purpose": "Refined scope and term definitions."},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "edited"
        assert data["provenance"][0]["bill_id"] == "bill-1"

    def test_get_detail_forbidden_returns_403(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        with patch(
            "src.api.policy_workspaces.get_workspace_detail",
            new_callable=AsyncMock,
        ) as mock_detail:
            mock_detail.side_effect = PermissionError(
                "Not authorized to access this policy workspace"
            )
            response = client.get(
                "/api/v1/policy-workspaces/workspace123",
                headers={"X-Client-Id": "client-2"},
            )

        assert response.status_code == 403

    def test_update_returns_200(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        updated_workspace = _mock_workspace(status="drafting", goal_prompt=None)

        with (
            patch(
                "src.api.policy_workspaces.get_workspace_for_client",
                new_callable=AsyncMock,
            ) as mock_get,
            patch(
                "src.api.policy_workspaces.update_workspace",
                new_callable=AsyncMock,
            ) as mock_update,
            patch(
                "src.api.policy_workspaces.get_workspace_detail",
                new_callable=AsyncMock,
            ) as mock_detail,
        ):
            mock_get.return_value = _mock_workspace()
            mock_update.return_value = updated_workspace
            mock_detail.return_value = updated_workspace

            response = client.patch(
                "/api/v1/policy-workspaces/workspace123",
                headers={"X-Client-Id": "client-1"},
                json={"status": "drafting", "goal_prompt": None},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "drafting"
        assert data["goal_prompt"] is None
        assert mock_update.await_args.kwargs["update_goal_prompt"] is True

    def test_add_precedent_returns_201(self, client):
        mock_session = AsyncMock()
        mock_session.refresh = AsyncMock(return_value=None)
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        with (
            patch(
                "src.api.policy_workspaces.get_workspace_for_client",
                new_callable=AsyncMock,
            ) as mock_get,
            patch("src.api.policy_workspaces.add_precedent", new_callable=AsyncMock) as mock_add,
        ):
            mock_get.return_value = _mock_workspace()
            mock_add.return_value = _mock_precedent()

            response = client.post(
                "/api/v1/policy-workspaces/workspace123/precedents",
                headers={"X-Client-Id": "client-1"},
                json={"bill_id": "bill-1"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["bill_id"] == "bill-1"
        assert data["identifier"] == "AB 101"

    def test_delete_precedent_returns_204(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        with (
            patch(
                "src.api.policy_workspaces.get_workspace_for_client",
                new_callable=AsyncMock,
            ) as mock_get,
            patch(
                "src.api.policy_workspaces.remove_precedent",
                new_callable=AsyncMock,
            ) as mock_remove,
        ):
            mock_get.return_value = _mock_workspace()
            response = client.delete(
                "/api/v1/policy-workspaces/workspace123/precedents/bill-1",
                headers={"X-Client-Id": "client-1"},
            )

        assert response.status_code == 204
        mock_remove.assert_awaited_once()

    def test_free_tier_blocked(self, client):
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="free")
        response = client.get("/api/v1/policy-workspaces", headers={"X-Client-Id": "client-1"})
        assert response.status_code == 403

    def test_compose_section_returns_pending_generation(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")
        app.dependency_overrides[get_llm_harness] = lambda: AsyncMock()

        gen = SimpleNamespace(
            id="gen-1",
            workspace_id="workspace123",
            section_id="section-1",
            action_type="draft_section",
            instruction_text=None,
            selected_text=None,
            output_payload={
                "content_markdown": "Section 1. Definitions.\n(a) ...",
                "rationale": "Based on precedent AB 101.",
            },
            provenance={
                "precedent_bill_ids": ["bill-1"],
                "sources": [
                    {
                        "bill_id": "bill-1",
                        "identifier": "AB 101",
                        "title": "Privacy Baseline Act",
                        "jurisdiction_id": "us-ca",
                        "note": "Definition section used as foundation.",
                    }
                ],
            },
            accepted_revision_id=None,
            created_at=datetime(2026, 3, 20),
        )

        with patch(
            "src.api.policy_workspaces.compose_section",
            new_callable=AsyncMock,
        ) as mock_compose:
            mock_compose.return_value = gen
            response = client.post(
                "/api/v1/policy-workspaces/workspace123/sections/section-1/compose",
                headers={"X-Client-Id": "client-1"},
                json={"action_type": "draft_section"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "gen-1"
        assert data["action_type"] == "draft_section"
        assert data["output_markdown"] == "Section 1. Definitions.\n(a) ..."
        assert data["accepted"] is False
        assert data["provenance"][0]["identifier"] == "AB 101"

    def test_compose_invalid_action_returns_400(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")
        app.dependency_overrides[get_llm_harness] = lambda: AsyncMock()

        with patch(
            "src.api.policy_workspaces.compose_section",
            new_callable=AsyncMock,
        ) as mock_compose:
            mock_compose.side_effect = ValueError("Invalid action type: bogus")
            response = client.post(
                "/api/v1/policy-workspaces/workspace123/sections/section-1/compose",
                headers={"X-Client-Id": "client-1"},
                json={"action_type": "bogus"},
            )

        assert response.status_code == 400

    def test_accept_generation_returns_updated_section(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        section = _mock_section(
            status="drafted",
            content_markdown="Section 1. Definitions.\n(a) ...",
        )
        workspace = _mock_workspace(
            status="drafting",
            sections=[section],
            generations=[_mock_generation()],
        )

        with (
            patch(
                "src.api.policy_workspaces.accept_generation",
                new_callable=AsyncMock,
            ) as mock_accept,
            patch(
                "src.api.policy_workspaces.get_workspace_detail",
                new_callable=AsyncMock,
            ) as mock_detail,
        ):
            mock_accept.return_value = SimpleNamespace(
                id="section-1",
                section_key="definitions",
                heading="Definitions",
                purpose="Define key terms.",
                position=0,
                content_markdown="Section 1. Definitions.\n(a) ...",
                status="drafted",
                created_at=datetime(2026, 3, 20),
                updated_at=datetime(2026, 3, 20),
            )
            mock_detail.return_value = workspace

            response = client.post(
                "/api/v1/policy-workspaces/workspace123/generations/gen-1/accept",
                headers={"X-Client-Id": "client-1"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "drafted"

    def test_accept_already_accepted_returns_400(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        with patch(
            "src.api.policy_workspaces.accept_generation",
            new_callable=AsyncMock,
        ) as mock_accept:
            mock_accept.side_effect = ValueError("Generation already accepted")
            response = client.post(
                "/api/v1/policy-workspaces/workspace123/generations/gen-1/accept",
                headers={"X-Client-Id": "client-1"},
            )

        assert response.status_code == 400
        assert "already accepted" in response.json()["detail"]

    def test_history_returns_revisions(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        rev = SimpleNamespace(
            id="rev-1",
            section_id="section-1",
            generation_id="gen-1",
            change_source="ai",
            content_markdown="Section 1. Definitions.\n(a) ...",
            created_at=datetime(2026, 3, 20),
        )

        with patch(
            "src.api.policy_workspaces.get_section_history",
            new_callable=AsyncMock,
        ) as mock_history:
            mock_history.return_value = [rev]
            response = client.get(
                "/api/v1/policy-workspaces/workspace123/history?section_id=section-1",
                headers={"X-Client-Id": "client-1"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["revisions"]) == 1
        assert data["revisions"][0]["change_source"] == "ai"
        assert data["revisions"][0]["generation_id"] == "gen-1"

    def test_export_returns_markdown(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="pro")

        with patch(
            "src.api.policy_workspaces.export_workspace_markdown",
            new_callable=AsyncMock,
        ) as mock_export:
            mock_export.return_value = (
                "# Privacy Model Act\n\n## Section 1. Definitions\n\nSample text."
            )
            response = client.get(
                "/api/v1/policy-workspaces/workspace123/export",
                headers={"X-Client-Id": "client-1"},
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert "# Privacy Model Act" in response.text
        assert "Section 1. Definitions" in response.text
