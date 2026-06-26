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
