"""A2 + A3a seams (no Postgres, no live LLM):
- lab_execute_tool: acks the lab-only submit_answer, routes everything else to the product reg;
- build_record's additive `extras` channel: a live solver's trajectory/raw/latency land in the
  trace, while deterministic solvers (extras=None) keep the original defaults unchanged.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from lab.graders import grade
from lab.harness import Instance
from lab.solvers import lab_execute_tool
from lab.trace import RunContext, build_record


class TestLabExecuteTool:
    async def test_submit_answer_is_acked_locally(self):
        out = json.loads(await lab_execute_tool("submit_answer", {"answer": "yea"}, None, None))
        assert out["status"] == "recorded"
        assert "do not call any more tools" in out["note"]  # directive: tells the agent to stop

    async def test_other_tools_route_to_product_registry(self):
        with patch(
            "src.api.chat.execute_tool", new=AsyncMock(return_value='{"ok": true}')
        ) as mock_exec:
            out = await lab_execute_tool("get_vote_event", {"vote_event_id": "X"}, "db", "harn")
        assert out == '{"ok": true}'
        mock_exec.assert_awaited_once_with("get_vote_event", {"vote_event_id": "X"}, "db", "harn")


def _inst() -> Instance:
    return Instance(
        instance_id="family1.vote_lookup:42:e1:p1",
        template_id="family1.vote_lookup",
        tier="C",
        params={"person_id": "p1", "vote_event_id": "e1"},
        prompt="How did X vote on e1?",
        gold="yea",
        grader="exact",
        is_refusal=False,
    )


class TestBuildRecordExtras:
    def test_agent_extras_populate_trace(self):
        inst = _inst()
        solver = SimpleNamespace(
            policy={"name": "agent", "model": "claude-sonnet-4-6"}, kind="agent"
        )
        verdict = grade(inst.grader, inst.gold, "yea", is_refusal=False)
        ctx = RunContext("c", "d", {})
        extras = {
            "trajectory": [{"tool_name": "get_vote_event", "args": {}, "result_summary": "ok"}],
            "raw": "Looking at the records, X voted yea.",
            "latency_ms": 1234.5,
        }
        rec = build_record(inst, solver, "yea", verdict, ctx, seed=42, extras=extras)
        assert rec.solver_kind == "agent"
        assert rec.trajectory == extras["trajectory"]
        assert rec.raw == "Looking at the records, X voted yea."
        assert rec.latency_ms == 1234.5
        assert rec.input_tokens is None and rec.cost is None  # deferred for Phase A

    def test_deterministic_defaults_unchanged_without_extras(self):
        inst = _inst()
        solver = SimpleNamespace(policy={"name": "oracle"}, kind="deterministic")
        verdict = grade(inst.grader, inst.gold, "yea", is_refusal=False)
        rec = build_record(inst, solver, "yea", verdict, RunContext("c", "d", {}), seed=42)
        assert rec.trajectory == []
        assert rec.raw == "yea"  # str(answer) default preserved
        assert rec.latency_ms is None


class TestTemplateTools:
    """Per-template tool provisioning (TEMPLATE_TOOLS) — the single source of truth both backends
    read. Event-keyed templates get get_vote_event; window-keyed templates get the window tools."""

    def test_event_templates_get_vote_event_only(self):
        from lab.solvers import TEMPLATE_TOOLS

        for tid in (
            "family1.vote_lookup",
            "family1.tally",
            "family1.party_breakdown",
            "family1.party_defection",
            "family1.crossed_party",
        ):
            assert TEMPLATE_TOOLS[tid] == ["get_vote_event"]

    def test_window_templates_get_minimal_window_subsets(self):
        from lab.solvers import TEMPLATE_TOOLS

        assert TEMPLATE_TOOLS["family1.closest_by_margin"] == ["list_vote_events"]
        member = ["find_people", "get_member_voting_record"]
        assert TEMPLATE_TOOLS["family1.member_summary"] == member
        assert TEMPLATE_TOOLS["family1.pairwise_agreement"] == member

    def test_template_tools_covers_every_registered_template(self):
        # P9: an unmapped template would KeyError at solve() time, mid-run, after spending tokens.
        # Key off ns.template_id (family-qualified), NOT f"family1.{name}" — Family 10 is the first
        # non-family-1 family, so the registry no longer encodes the family in its bare-name key.
        from lab import templates
        from lab.solvers import TEMPLATE_TOOLS

        registered = {ns.template_id for ns in templates.TEMPLATE_REGISTRY.values()}
        missing = registered - set(TEMPLATE_TOOLS)
        assert not missing, f"unmapped templates: {missing}"

    def test_research_tool_for_resolves_every_provisioned_tool(self):
        from lab.solvers import TEMPLATE_TOOLS, research_tool_for

        for names in TEMPLATE_TOOLS.values():
            for name in names:
                assert research_tool_for(name)["name"] == name
