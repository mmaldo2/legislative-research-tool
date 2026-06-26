"""SWAPPABLE solvers used to validate the GRADERS without a live LLM (v1).

  - SqlOracleSolver: returns gold -> graders must PASS (they accept correct answers).
  - WrongBaselineSolver: returns a wrong answer -> graders must FAIL (catch hallucinations).
  - OverRefuseSolver: refuses everything -> answerable items FAIL (catches over-refusal).

AgentSolver (kind="agent") is the live LLM solver: it drives the production run_agentic_chat loop
(anthropic-oauth backend) over {get_vote_event, submit_answer} and is NOT invariant-checked (its
pass rate is the measurement). Each solver exposes `kind` + `policy` so the trace records what
produced a rollout (and synthetic deterministic rows stay filterable from live agent rollouts).
"""

import asyncio
import json
import time

from lab.graders import REFUSAL
from lab.harness import Instance
from src.ingestion.vote_parsers import OPTION_BUCKETS


class _DeterministicSolver:
    """Base for the non-LLM validation solvers: a fixed policy + a synthetic-row marker."""

    name: str
    kind = "deterministic"

    @property
    def policy(self) -> dict:
        return {"name": self.name}


class SqlOracleSolver(_DeterministicSolver):
    name = "oracle"

    def solve(self, inst: Instance):
        return inst.gold


class WrongBaselineSolver(_DeterministicSolver):
    """Provably wrong per instance, but always WELL-FORMED (so the wrong-baseline invariant is
    decision_correct==1 & answer_correct==0 & format_valid==1, never a format-fail):
      - refusal item:  fabricate a non-refusal option (didn't refuse -> wrong);
      - dict gold:     perturb the first non-bool int field by +1 (same keys -> shape valid);
      - set gold:      ADD a guaranteed-absent sentinel (never remove -> empty gold stays wrong);
      - bare int gold: +1 (a well-formed wrong int -> attempted-but-wrong, not a format-fail);
      - scalar option: a different valid option.
    """

    name = "wrong-baseline"

    def solve(self, inst: Instance):
        if inst.is_refusal:
            return OPTION_BUCKETS[0]  # fabricate instead of refusing -> wrong
        gold = inst.gold
        if isinstance(gold, dict):
            for key, val in gold.items():
                if isinstance(val, int) and not isinstance(val, bool):
                    return {**gold, key: val + 1}
            raise AssertionError(f"composite gold has no int field to perturb: {gold!r}")
        if isinstance(gold, set | list | tuple):
            return set(gold) | {"NX-wrong"}  # add a provably-absent id
        if isinstance(gold, int) and not isinstance(gold, bool):
            return gold + 1  # bare int (e.g. defection count) -> a different, well-formed int
        for opt in OPTION_BUCKETS:
            if opt != gold:
                return opt
        return REFUSAL  # unreachable for a valid option gold


class OverRefuseSolver(_DeterministicSolver):
    """Refuses every item — proves the exact grader catches over-refusal on answerable items."""

    name = "over-refuse"

    def solve(self, inst: Instance):
        return REFUSAL


# --- Lab agent tools (used by the live AgentSolver) -------------------------------------------
# submit_answer is a LAB-ONLY meta-tool — deliberately NOT a product RESEARCH_TOOL — the agent's
# structured, typed answer channel (no prose parsing). get_vote_event IS a product tool.

SUBMIT_ANSWER_TOOL = {
    "name": "submit_answer",
    "description": (
        "Call this exactly once to submit your final answer and finish. Set refused=true ONLY if "
        "the member asked about is not present in the vote data you retrieved; otherwise put that "
        "member's recorded vote in `answer`, copied VERBATIM from their `option` field in "
        "get_vote_event (one of: yea, nay, present, not_voting). Do not set both."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "The member's recorded option, copied verbatim from get_vote_event.",
            },
            "refused": {
                "type": "boolean",
                "description": "True iff the answer is not present in the retrieved data.",
                "default": False,
            },
        },
    },
}


async def lab_execute_tool(tool_name: str, arguments: dict, db, harness) -> str:
    """ToolExecutor for the lab agent run: `submit_answer` is a local sink (the payload is read
    from `all_tool_calls` by the solver); every other tool (e.g. `get_vote_event`) routes to the
    real product registry."""
    if tool_name == "submit_answer":
        return json.dumps({"status": "recorded"})
    from src.api.chat import execute_tool  # lazy: keep product code off the deterministic path

    return await execute_tool(tool_name, arguments, db, harness)


# A non-REFUSAL, non-canonical sentinel: a crashed/non-finishing agent must FORMAT-FAIL on BOTH
# arms (never earn free refusal credit on a refusal instance). It is its own filterable value.
NO_ANSWER = "__no_answer__"

_AGENT_SYSTEM_PROMPT = (
    "You answer factual questions about U.S. Congressional roll-call votes. Use the get_vote_event "
    "tool to retrieve a roll call's records, find the member named in the question, and read their "
    "recorded vote. Then call submit_answer exactly once with that member's option copied VERBATIM "
    "(yea / nay / present / not_voting). If the member named is not present in the retrieved "
    "records, call submit_answer with refused=true. Never guess."
)


def _map_answer(tool_calls: list[dict]):
    """Project the agent's tool trajectory into a typed answer. The structured `refused` flag is
    AUTHORITATIVE; a non-canonical `answer` is passed THROUGH (it format-fails at grading, which is
    honest — not snapped to a valid option). Inconsistent (both / neither) and never-submitted all
    collapse to NO_ANSWER so they fail cleanly without crashing."""
    submits = [tc for tc in tool_calls if tc.get("tool_name") == "submit_answer"]
    if not submits:
        return NO_ANSWER  # agent never finished (gave up / hit max_rounds)
    args = submits[-1].get("arguments") or {}
    refused = bool(args.get("refused", False))
    answer = args.get("answer")
    # a literal REFUSAL sentinel in `answer` must NOT back-door refusal credit when refused is false
    has_answer = isinstance(answer, str) and answer != "" and answer != REFUSAL
    if refused and has_answer:
        return NO_ANSWER  # inconsistent: both set
    if refused:
        return REFUSAL
    if has_answer:
        return answer
    return NO_ANSWER  # neither set (or answer == the REFUSAL sentinel)


class AgentSolver:
    """The live LLM solver: drives the production `run_agentic_chat` loop constrained to
    {get_vote_event, submit_answer}, maps the submit_answer payload to a typed answer, and publishes
    `trace_extras` (trajectory + prose + latency) for the additive trace seam. NOT invariant-checked
    (a live agent is non-deterministic); its pass rate is the measurement.
    """

    name = "agent"
    kind = "agent"

    def __init__(
        self, *, model: str = "claude-sonnet-4-6", client=None, system_prompt: str | None = None
    ):
        self.model = model
        self._client = client  # injectable (tests pass a Mock; prod builds the OAuth client lazily)
        self.system_prompt = system_prompt or _AGENT_SYSTEM_PROMPT
        self.trace_extras: dict | None = None
        self._runner: asyncio.Runner | None = None

    @property
    def policy(self) -> dict:
        # strings only — NEVER the client or the auth token
        return {
            "name": self.name,
            "backend": "anthropic-oauth",
            "model": self.model,
            "system_prompt_id": "lab_vote_lookup_v1",
        }

    def _client_or_build(self):
        if self._client is None:
            from src.api.deps import get_oauth_anthropic_client

            self._client = get_oauth_anthropic_client()
        return self._client

    def solve(self, inst: Instance):
        # ONE persistent loop for the solver's lifetime: a fresh asyncio.run() per instance would
        # bind pooled asyncpg connections to a loop it then closes, crashing the next instance.
        if self._runner is None:
            self._runner = asyncio.Runner()
        answer, extras = self._runner.run(self._asolve(inst))
        self.trace_extras = extras  # read by solve_grade_write right after solve()
        return answer

    async def _asolve(self, inst: Instance):
        from src.llm.tools import RESEARCH_TOOLS
        from src.services.chat_service import run_agentic_chat

        get_vote_event = next(t for t in RESEARCH_TOOLS if t["name"] == "get_vote_event")
        # PROMPT ONLY — never inst.params (holds the gold person_id) or inst.gold.
        messages = [{"role": "user", "content": inst.prompt}]
        started = time.monotonic()
        final_text, tool_calls = await run_agentic_chat(
            system_prompt=self.system_prompt,
            messages=messages,
            client=self._client_or_build(),
            tools=[get_vote_event, SUBMIT_ANSWER_TOOL],
            execute_tool_fn=lab_execute_tool,
            model=self.model,
        )
        latency_ms = (time.monotonic() - started) * 1000
        answer = _map_answer(tool_calls)
        extras = {"trajectory": tool_calls, "raw": final_text, "latency_ms": latency_ms}
        return answer, extras

    def close(self) -> None:
        if self._runner is not None:
            self._runner.close()
            self._runner = None
