"""SWAPPABLE solvers used to validate the GRADERS without a live LLM (v1).

  - SqlOracleSolver: returns gold -> graders must PASS (they accept correct answers).
  - WrongBaselineSolver: returns a wrong answer -> graders must FAIL (catch hallucinations).
  - OverRefuseSolver: refuses everything -> answerable items FAIL (catches over-refusal).

AgentSolver (kind="agent") is the live LLM solver over {get_vote_event, submit_answer}, with two
backends (messages-api = Option X, the run_agentic_chat loop; agent-sdk = Option W, the in-process
Agent SDK). It is NOT invariant-checked — its pass rate is the measurement. Each solver exposes
`kind` + `policy` so the trace records what produced a rollout (deterministic rows stay filterable
from live agent rollouts, and agent rollouts stay filterable by backend).
"""

import asyncio
import json
import math
import re
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

# SHAPE-AWARE submit_answer: per-template typed fields. The answer fields are OPTIONAL (only the
# fields the agent chooses are filled; a bare {refused: true} is a valid refusal). Field NAMES +
# descriptions restate the QUESTION's quantities — NEVER the answer VALUES or the computation METHOD
# (leak-safe). `fields` golds are built from GOLD_KEYS so answer.keys() == gold.keys() exactly.
GOLD_KEYS = {
    "family1.tally": ("yea", "nay", "margin", "result"),
    "family1.party_breakdown": ("yea", "nay"),
    "family1.member_summary": ("yea", "nay", "other"),
    "family1.pairwise_agreement": ("agreements", "shared_events"),
}
NUMERIC_FIELDS = {
    "family1.tally": ("yea", "nay", "margin"),
    "family1.party_breakdown": ("yea", "nay"),
    # P8: member_summary + pairwise golds are ALL-int -> NUMERIC_FIELDS == GOLD_KEYS (no str field
    # like tally's `result`), else a stringized "5" would str()-through and false-fail.
    "family1.member_summary": ("yea", "nay", "other"),
    "family1.pairwise_agreement": ("agreements", "shared_events"),
}
_REFUSED_FIELD = {
    "refused": {
        "type": "boolean",
        "description": "True iff the event or member asked about is not in the retrieved data.",
        "default": False,
    }
}
SUBMIT_SCHEMAS = {
    "family1.vote_lookup": {
        "answer": {
            "type": "string",
            "description": "The member's recorded option (yea/nay/present/not_voting), copied "
            "verbatim from get_vote_event.",
        },
        **_REFUSED_FIELD,
    },
    "family1.tally": {
        "yea": {"type": "integer", "description": "The number of yea votes."},
        "nay": {"type": "integer", "description": "The number of nay votes."},
        "margin": {"type": "integer", "description": "Yea count minus nay count."},
        "result": {
            "type": "string",
            "description": "The recorded result, copied verbatim from get_vote_event.",
        },
        **_REFUSED_FIELD,
    },
    "family1.party_breakdown": {
        "yea": {"type": "integer", "description": "The number of the party who voted yea."},
        "nay": {"type": "integer", "description": "The number of the party who voted nay."},
        **_REFUSED_FIELD,
    },
    "family1.party_defection": {
        "count": {
            "type": "integer",
            "description": "The integer count the question asks for (a number of members).",
        },
        **_REFUSED_FIELD,
    },
    "family1.crossed_party": {
        "member_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The member ids the question asks you to list (an empty list if none).",
        },
        **_REFUSED_FIELD,
    },
    "family1.member_summary": {
        "yea": {
            "type": "integer",
            "description": "The number of roll calls on which the member voted yea.",
        },
        "nay": {
            "type": "integer",
            "description": "The number of roll calls on which the member voted nay.",
        },
        "other": {
            "type": "integer",
            "description": "The number of roll calls on which the member voted other (present or "
            "not voting).",
        },
        **_REFUSED_FIELD,
    },
    "family1.pairwise_agreement": {
        "agreements": {
            "type": "integer",
            "description": "The number of roll calls on which both members cast the identical "
            "option.",
        },
        "shared_events": {
            "type": "integer",
            "description": "The number of roll calls on which both members cast a yea or nay vote.",
        },
        **_REFUSED_FIELD,
    },
    "family1.closest_by_margin": {
        "roll_call_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The roll-call ids the question asks you to list.",
        },
        **_REFUSED_FIELD,
    },
}

# set_match is keyed per-template (the submit field NAME differs: crossed lists members, closest
# lists roll calls) — coerce + _answer_present resolve the field via this map, not a literal.
SET_MATCH_FIELD = {
    "family1.crossed_party": "member_ids",
    "family1.closest_by_margin": "roll_call_ids",
}

_SUBMIT_DESCRIPTION = (
    "Call this exactly once to submit your final answer and finish. Fill the answer fields the "
    "question asks for. To refuse, set refused=true and leave the answer fields empty. Do not set "
    "both. After this, end your turn — do not call any more tools."
)


def submit_tool_for(template_id: str) -> dict:
    """The shape-aware submit_answer tool for a template (answer fields OPTIONAL → a bare
    {refused: true} is a valid refusal)."""
    return {
        "name": "submit_answer",
        "description": _SUBMIT_DESCRIPTION,
        "input_schema": {"type": "object", "properties": SUBMIT_SCHEMAS[template_id]},
    }


# PER-TEMPLATE TOOL PROVISIONING: each template is offered exactly the product tools it needs (plus
# submit_answer, appended by the backends). Event-keyed templates use get_vote_event; window-keyed
# templates use the multi-event window tools. Minimal exact subsets — closest must not be tempted to
# call find_people, member_summary must not be tempted toward list_vote_events. Both backends read
# THIS single map (the parity mechanism).
_EVENT_TOOLS = ["get_vote_event"]
_MEMBER_TOOLS = ["find_people", "get_member_voting_record"]
TEMPLATE_TOOLS = {
    "family1.vote_lookup": _EVENT_TOOLS,
    "family1.tally": _EVENT_TOOLS,
    "family1.party_breakdown": _EVENT_TOOLS,
    "family1.party_defection": _EVENT_TOOLS,
    "family1.crossed_party": _EVENT_TOOLS,
    "family1.closest_by_margin": ["list_vote_events"],
    "family1.member_summary": _MEMBER_TOOLS,
    "family1.pairwise_agreement": _MEMBER_TOOLS,
}


def research_tool_for(name: str) -> dict:
    """The product RESEARCH_TOOLS def for a tool name (lazy import keeps product code off the
    deterministic path). Raises loudly on a wiring typo (the name comes from TEMPLATE_TOOLS)."""
    from src.llm.tools import RESEARCH_TOOLS

    return next(t for t in RESEARCH_TOOLS if t["name"] == name)


async def lab_execute_tool(tool_name: str, arguments: dict, db, harness) -> str:
    """ToolExecutor for the lab agent run: `submit_answer` is a local sink (the payload is read
    from `all_tool_calls` by the solver); every other tool (e.g. `get_vote_event`) routes to the
    real product registry."""
    if tool_name == "submit_answer":
        return json.dumps(
            {
                "status": "recorded",
                "note": "Answer recorded. You are finished — do not call any more tools; "
                "end your turn now.",
            }
        )
    from src.api.chat import execute_tool  # lazy: keep product code off the deterministic path

    return await execute_tool(tool_name, arguments, db, harness)


# A non-REFUSAL, non-canonical sentinel: a crashed/non-finishing agent must FORMAT-FAIL on BOTH
# arms (never earn free refusal credit on a refusal instance). It is its own filterable value.
NO_ANSWER = "__no_answer__"

_SECRET_RE = re.compile(r"sk-ant-[A-Za-z0-9_-]+")


def _safe_err(exc: Exception, limit: int = 300) -> str:
    """Defense-in-depth: a live API error is persisted into the trace `raw`. Redact any OAuth token
    that could appear in a third-party error string and bound the length, so no secret / unbounded
    blob reaches the at-rest JSONL."""
    msg = _SECRET_RE.sub("<redacted>", str(exc))
    if len(msg) > limit:
        msg = msg[:limit] + "…(truncated)"
    return f"<agent error: {type(exc).__name__}: {msg}>"


_AGENT_SYSTEM_PROMPT = (
    "You answer factual questions about U.S. Congressional roll-call votes. Use the available "
    "retrieval tools to gather the relevant vote records, then COMPUTE the answer the question "
    "asks for from those records (counting members, reading the recorded option, ranking by "
    "margin, etc.). Give your final answer ONLY by calling submit_answer exactly once, filling the "
    "structured fields the question asks for — do NOT answer in prose. ALWAYS finish by calling "
    "submit_answer; if a retrieval tool reports the event, member, or window is not in the data "
    "(an error or an empty result), you MUST still call submit_answer with refused=true (and do "
    "NOT fill the answer fields) — never stop without calling submit_answer. Never guess; compute "
    "from the records."
)


def _to_int(value) -> int | None:
    """Total int coercion shared by exact_int AND the fields numeric path. A wrong value is NEVER
    snapped to a right one: 3.7 -> None (reject), "5" -> 5, "5.0"/"abc" -> None, bool -> None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value == int(value) else None
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def coerce(grader: str, template_id: str, payload: dict):
    """Grader-dispatched, TOTAL coercion of the submit_answer payload to the grader's expected type
    (NO_ANSWER on anything malformed — never crashes). Deliberate asymmetry: a bare non-int for
    exact_int -> NO_ANSWER (format-fail); a non-coercible fields sub-value -> kept raw -> graded
    attempted-but-wrong (the dict still carries the gold key-set)."""
    try:
        if grader == "exact":
            ans = payload.get("answer")
            return ans if isinstance(ans, str) else NO_ANSWER
        if grader == "exact_int":
            n = _to_int(payload.get("count"))
            return n if n is not None else NO_ANSWER
        if grader == "fields":
            numeric = NUMERIC_FIELDS[template_id]
            out: dict = {}
            for key in GOLD_KEYS[template_id]:
                raw = payload.get(key)
                if key in numeric:
                    n = _to_int(raw)
                    out[key] = n if n is not None else raw  # raw -> attempted-but-wrong
                else:
                    out[key] = str(raw) if raw is not None else None
            return out
        if grader == "set_match":
            ids = payload.get(SET_MATCH_FIELD[template_id])  # per-template field name (P1)
            if not isinstance(ids, list | tuple):  # a str/dict is iterable -> would mis-grade
                return NO_ANSWER
            return [str(x) for x in ids]
        return NO_ANSWER
    except Exception:  # noqa: BLE001 — TOTAL: any malformed payload -> NO_ANSWER, never crash the run
        return NO_ANSWER


def _answer_present(grader: str, template_id: str, args: dict) -> bool:
    """Per-grader 'did the agent fill a substantive answer?' (vs a bare refusal). An explicit empty
    member_ids list IS an answer (∅ crossers), not a refusal."""
    if grader == "exact":
        a = args.get("answer")
        return isinstance(a, str) and a != "" and a != REFUSAL
    if grader == "exact_int":
        return args.get("count") is not None
    if grader == "fields":
        return any(args.get(k) is not None for k in GOLD_KEYS[template_id])
    if grader == "set_match":
        return args.get(SET_MATCH_FIELD[template_id]) is not None  # per-template field name (P1)
    return False


def _map_answer(tool_calls: list[dict], *, grader: str, template_id: str):
    """Project the agent's tool trajectory into a typed answer, uniform across shapes. `refused` is
    authoritative ONLY when no substantive answer is present; inconsistent (both) / neither /
    never-submitted -> NO_ANSWER (format-fails every grader; no free refusal credit)."""
    submits = [tc for tc in tool_calls if tc.get("tool_name") == "submit_answer"]
    if not submits:
        return NO_ANSWER  # agent never finished
    args = submits[-1].get("arguments") or {}
    refused = bool(args.get("refused", False))
    present = _answer_present(grader, template_id, args)
    if refused and present:
        return NO_ANSWER  # inconsistent: both set
    if refused:
        return REFUSAL
    if present:
        return coerce(grader, template_id, args)
    return NO_ANSWER  # neither set


# BENCHMARK-INTEGRITY: the Agent SDK exposes the claude CLI's built-in tools. Disallow them so the
# agent can ONLY use the lab's get_vote_event + submit_answer (it must not shell out / read gold off
# disk / discover other tools). allowed_tools whitelists the two lab tools; this is the belt.
_DISALLOWED_BUILTINS = [
    "Bash",
    "BashOutput",
    "KillShell",
    "Read",
    "Write",
    "Edit",
    "NotebookEdit",
    "Glob",
    "Grep",
    "WebFetch",
    "WebSearch",
    "Task",
    "TodoWrite",
    "ToolSearch",
    "Skill",
    "Agent",
]


def _make_sdk_product_tool(tool_def: dict, observations: list):
    """Wrap a product RESEARCH_TOOL as an in-process Agent SDK @tool: it opens its OWN
    async_session_factory session, routes through the SAME lab_execute_tool seam as Option X (data
    parity), and records a BARE-name observation. The closure binds its own `tool_def` +
    `observations` (no late-binding when building N tools in a comprehension)."""
    from claude_agent_sdk import tool

    name = tool_def["name"]

    @tool(name, tool_def["description"], tool_def["input_schema"])
    async def _product_tool(args):
        from src.database import async_session_factory

        async with async_session_factory() as db:  # @tool opens its OWN session on this loop
            result = await lab_execute_tool(name, args, db, None)
        observations.append({"tool": name, "arguments": dict(args), "result": result})
        return {"content": [{"type": "text", "text": result}]}

    return _product_tool


class AgentSolver:
    """The live LLM solver over {get_vote_event, submit_answer}, constrained to the per-template
    shape-aware submit_answer. `backend` selects messages-api (Option X, run_agentic_chat) or
    agent-sdk (Option W, in-process Agent SDK); both share `_map_answer`/SUBMIT_SCHEMAS/trace_extras
    and differ only in loop-drive + capture. Maps the submit_answer payload to the grader's typed
    answer. NOT invariant-checked (non-deterministic); its pass rate is the measurement.
    """

    name = "agent"
    kind = "agent"

    def __init__(
        self,
        *,
        model: str = "claude-sonnet-4-6",
        client=None,
        system_prompt: str | None = None,
        backend: str = "messages-api",
    ):
        self.model = model
        self.backend = backend  # "messages-api" (Option X) | "agent-sdk" (Option W)
        self._client = client  # injectable (tests pass a Mock; prod builds the OAuth client lazily)
        self.system_prompt = system_prompt or _AGENT_SYSTEM_PROMPT
        self.trace_extras: dict | None = None
        self.history: list[dict] = []  # per-instance diagnostic trail (retrieved? errored?)
        self._runner: asyncio.Runner | None = None

    @property
    def policy(self) -> dict:
        # strings only — NEVER the client or the auth token
        return {
            "name": self.name,
            "backend": self.backend,
            "model": self.model,
            "system_prompt_id": "lab_family1_v1",
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
        # Diagnostic trail (read by run.py's agent summary; never affects grading):
        self.history.append(
            {
                "instance_id": inst.instance_id,
                "is_refusal": inst.is_refusal,
                # any product (non-submit) tool call counts as retrieval (bare tool name; the SDK
                # backend records the bare name too) — generalizes beyond get_vote_event.
                "retrieved": any(
                    o.get("tool") not in (None, "submit_answer")
                    for o in extras.get("trajectory", [])
                ),
                "errored": str(extras.get("raw", "")).startswith("<agent error:"),
                "result_subtype": extras.get("result_subtype"),  # P7: SDK stop reason (or None)
            }
        )
        return answer

    async def _asolve(self, inst: Instance):
        if self.backend == "agent-sdk":
            return await self._asolve_sdk(inst)
        return await self._asolve_messages(inst)

    async def _asolve_messages(self, inst: Instance):
        from src.services.chat_service import run_agentic_chat

        # Per-template tool subset (TEMPLATE_TOOLS) + the shape-aware submit_answer.
        tools = [research_tool_for(n) for n in TEMPLATE_TOOLS[inst.template_id]]
        tools.append(submit_tool_for(inst.template_id))
        # PROMPT ONLY — never inst.params (holds the gold person_id) or inst.gold.
        messages = [{"role": "user", "content": inst.prompt}]

        # Capture the agent's OBSERVATIONS (the FULL tool results it actually saw, not the
        # char-count summaries run_agentic_chat returns) so the trace is rich enough to read/train
        # on — lab_execute_tool already has the full result in hand.
        observations: list[dict] = []

        async def _record(tool_name, arguments, db, harness):
            result = await lab_execute_tool(tool_name, arguments, db, harness)
            observations.append({"tool": tool_name, "arguments": arguments, "result": result})
            return result

        started = time.monotonic()
        try:
            final_text, tool_calls = await run_agentic_chat(
                system_prompt=self.system_prompt,
                messages=messages,
                client=self._client_or_build(),
                tools=tools,
                execute_tool_fn=_record,
                model=self.model,
            )
        except Exception as exc:  # noqa: BLE001
            # A live API/network failure FAILS this instance (NO_ANSWER) but must NEVER crash the
            # run — one rate-limit shouldn't lose every other rollout. The error is recorded
            # (redacted) in the trace (raw) and the partial observations are kept.
            return NO_ANSWER, {
                "trajectory": observations,
                "raw": _safe_err(exc),
                "latency_ms": (time.monotonic() - started) * 1000,
            }
        # NB: keep _map_answer OUTSIDE the try — a mapping/harness bug must crash loudly, not be
        # silently mislabeled as an agent error.
        latency_ms = (time.monotonic() - started) * 1000
        answer = _map_answer(tool_calls, grader=inst.grader, template_id=inst.template_id)
        extras = {"trajectory": observations, "raw": final_text, "latency_ms": latency_ms}
        return answer, extras

    async def _asolve_sdk(self, inst: Instance):
        """Option W: drive the in-process Agent SDK (subscription-native, no rate wall). Builds a
        fresh in-process MCP server per instance (fresh capture closures); the @tools route through
        the SAME lab_execute_tool seam as Option X (data parity) + record bare-name observations.
        Constrained to the template's tool subset (TEMPLATE_TOOLS); built-ins disallowed."""
        import os

        from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server, query, tool
        from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

        observations: list[dict] = []
        submit_box: list[dict] = []

        # Per-template product @tools (single source of truth: TEMPLATE_TOOLS) + the shape-aware
        # submit; allowed_tools derives from the SAME list (P9 lockstep — the whitelist can't drift
        # wider/narrower than the provisioned set).
        tool_names = TEMPLATE_TOOLS[inst.template_id]
        product_tools = [
            _make_sdk_product_tool(research_tool_for(n), observations) for n in tool_names
        ]

        submit_schema = {"type": "object", "properties": SUBMIT_SCHEMAS[inst.template_id]}

        @tool("submit_answer", _SUBMIT_DESCRIPTION, submit_schema)
        async def _sdk_submit(args):
            submit_box.append(dict(args))
            ack = await lab_execute_tool("submit_answer", args, None, None)
            observations.append({"tool": "submit_answer", "arguments": dict(args), "result": ack})
            return {"content": [{"type": "text", "text": ack}]}

        server = create_sdk_mcp_server(name="lab", tools=[*product_tools, _sdk_submit])
        allowed_tools = [f"mcp__lab__{n}" for n in tool_names] + ["mcp__lab__submit_answer"]
        # subscription creds ONLY: pop ANTHROPIC_API_KEY so query() can't silently bill the Messages
        # API (and hit the rate wall Option W exists to dodge); restored in finally.
        saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        options = ClaudeAgentOptions(
            model=self.model,
            mcp_servers={"lab": server},
            allowed_tools=allowed_tools,
            disallowed_tools=_DISALLOWED_BUILTINS,
            permission_mode="bypassPermissions",
            setting_sources=[],  # no ambient CLAUDE.md / .claude config / project MCP servers
            max_turns=14,  # headroom for the largest windows (sonnet hit 10 on a 1138-event pairwise)
            max_budget_usd=6.0,  # per-rollout guard ($3 truncated the largest sonnet window rollouts)
            system_prompt=self.system_prompt,
        )
        started = time.monotonic()
        text_parts: list[str] = []
        cost = None
        result_subtype = None  # P7: SDK stop reason — tells truncation apart from a wrong answer
        try:
            async for msg in query(prompt=inst.prompt, options=options):  # PROMPT ONLY
                if isinstance(msg, AssistantMessage):
                    text_parts.extend(b.text for b in msg.content if isinstance(b, TextBlock))
                elif isinstance(msg, ResultMessage):
                    cost = getattr(msg, "total_cost_usd", None)
                    result_subtype = getattr(msg, "subtype", None)
        except Exception as exc:  # noqa: BLE001 — a live failure FAILS the instance, never crashes
            return NO_ANSWER, {
                "trajectory": observations,
                "raw": _safe_err(exc),
                "latency_ms": (time.monotonic() - started) * 1000,
            }
        finally:
            if saved_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = saved_key
        # _map_answer OUTSIDE the try (mapper bugs crash loudly); input is backend-agnostic.
        latency_ms = (time.monotonic() - started) * 1000
        tool_calls = (
            [{"tool_name": "submit_answer", "arguments": submit_box[-1]}] if submit_box else []
        )
        answer = _map_answer(tool_calls, grader=inst.grader, template_id=inst.template_id)
        extras = {
            "trajectory": observations,
            "raw": "\n".join(text_parts),
            "latency_ms": latency_ms,
            "cost": cost,
            "result_subtype": result_subtype,
        }
        return answer, extras

    def close(self) -> None:
        """Terminal — do not reuse the solver after close(). Dispose the shared async engine's pool
        on the Runner's loop BEFORE closing it, so asyncpg connections aren't orphaned on a dead
        loop ('Event loop is closed' GC noise)."""
        if self._runner is not None:
            try:
                from src.database import engine

                self._runner.run(engine.dispose())
            except Exception:  # noqa: BLE001 — best-effort cleanup; never mask the real result
                pass
            self._runner.close()
            self._runner = None
