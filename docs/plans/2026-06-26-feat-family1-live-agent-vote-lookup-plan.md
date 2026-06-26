---
title: "feat: Family 1 live-agent slice (Phase A — vote_lookup)"
type: feat
status: active
date: 2026-06-26
revision: 2  # rev 2 after the 5-lens adversarial panel (2 blockers + integrity MAJORs folded)
---

# Family 1 live-agent slice — Phase A (vote_lookup)

## Overview

Build the **first live-LLM agent run** over the frozen Family 1 graded-task harness, proving the
end-to-end loop on the simplest scalar template (`vote_lookup`) before widening. Today **no
`RESEARCH_TOOL` exposes vote data** — `get_bill_detail` even advertises "vote history" but never loads
`vote_events` — so the chat/MCP agent literally cannot answer a Family 1 question. This slice adds the
missing vote tool, a structured answer channel, and a lab `AgentSolver` that drives the agentic loop,
grades with the **unchanged frozen graders**, and writes a `solver_kind="agent"` trace **carrying the
agent's full tool trajectory + prose** (the training artifact this milestone exists to produce).

The agent's pass rate is a **measurement, not a target** — we never weaken a gate/grader to make it
pass. Rev 2 incorporates the 5-lens panel: two blockers resolved (trace-capture seam; event-loop/pool
hazard), the refusal mechanism corrected, gold-leak/fallback/duplicate-name integrity guards added,
and Decision 0's fallback set to the in-process Agent SDK (Option W).

## Blessed / locked decisions (design chat — do NOT re-open)

- **`get_vote_event(vote_event_id)`** — a NEW REAL product `RESEARCH_TOOL` (schema in
  `src/llm/tools.py`, async handler in `src/api/chat.py::_TOOL_HANDLERS`). Returns the event's stored
  counts + per-member `(person_id, name, option, vote-time party)` rows; party via the half-open
  `person_party_spans` as-of join (`start_date <= vote_date < end_date`), **never `people.party`**. RAW
  rows, not aggregates. Serves 5 of 8 templates; the window/member-spanning 3 need a second tool —
  **OUT OF SCOPE (Phase B)**.
- **`submit_answer`** — a LAB-ONLY structured tool; payload = typed answer + a `refused` boolean.
  Deterministic typed extraction. Grader stays `exact`/`refusal_correct` — **NO new grader mode**.
- **`AgentSolver`** (`lab/solvers.py`, swappable slot) — `kind="agent"`, drives the agentic loop, maps
  `submit_answer` → typed answer. `policy` = agent config (strings only — backend/model/prompt-id).
- **First slice = `vote_lookup` only.**

### Blessed in rev 2 (from the panel):
- **Decision 1 — additive trace-capture seam** (B1): `solve()` may publish `self.trace_extras`;
  `solve_grade_write` + `build_record` thread it into `trajectory`/`raw`/`latency_ms`. **Additive,
  moves NEITHER hash** (`harness.py`/`trace.py` are in neither the contract nor content hash set), and
  deterministic solvers (no `trace_extras`) are byte-for-byte unaffected.
- **Decision 0 fallback = Option W** (in-process Agent SDK) on spike-fail; Option X stays primary.

## Decision 0 — backend + loop (spike-gated)

`run_agentic_chat`'s `ClaudeSDKClient` adapter **ignores `tools=` and hardcodes `stop_reason="end_turn"`**
(`src/llm/claude_sdk_adapter.py`), so the claude-sdk client cannot drive app-loop tool use.
`anthropic_auth_token` is config-defined but **never read** by `get_llm_client` (`src/api/deps.py`).

| Path | Tool subset | submit_answer capture | Auth / cost | Loop fidelity | Role |
|---|---|---|---|---|---|
| **X. `run_agentic_chat` + real `anthropic.AsyncAnthropic(auth_token=…)`** | ✅ per-call `tools=` | ✅ `all_tool_calls` | OAuth (spike) / else metered key | **production loop** | **PRIMARY** |
| **W. in-process Agent SDK** (`create_sdk_mcp_server` + `@tool` + `allowed_tools`) | ✅ | ✅ from SDK event stream | subscription, **$0, works today** | SDK loop | **blessed FALLBACK** |
| Y. MCP subprocess (`stream_sdk_agentic_chat`) | ❌ all 10 tools | ⚠️ event stream | subscription | SDK loop | rejected (heavy; bypassPermissions) |

- **Phase 0 spike** decides X vs W: does `.env` `ANTHROPIC_AUTH_TOKEN` (`sk-ant-oat01`) authenticate the
  **Messages API** via `AsyncAnthropic(auth_token=...)`?
  - **Pass** → Option X (production-loop fidelity, $0). Wire the client via a NEW named helper
    `get_oauth_anthropic_client()` in `src/api/deps.py` reading `settings.anthropic_auth_token`
    (env-backed, **never hardcoded**), injectable into `AgentSolver`.
  - **Fail** → Option W (blessed): re-scope A2/A3 to the in-process Agent SDK (custom `@tool`
    wrappers for `get_vote_event`/`submit_answer`, `allowed_tools` subset, `permission_mode` set; NO
    product MCP-server change). Only escalate to a metered `ANTHROPIC_API_KEY` if W is also blocked.

## Architecture (files touched)

| File | Change | Hash impact |
|---|---|---|
| `src/llm/tools.py` | + `get_vote_event` schema; fix `get_bill_detail` description | product |
| `src/api/chat.py` | + `_tool_get_vote_event` (bound ORM params; `try/except Exception`→`{"error"}`); register in `_TOOL_HANDLERS` (NOT `_HARNESS_REQUIRED_TOOLS`) | product |
| `src/api/deps.py` | + `get_oauth_anthropic_client()` (Option X) reading `settings.anthropic_auth_token` | product |
| `src/services/chat_service.py` | + optional `model` param on `run_agentic_chat` (default `settings.summary_model`) | product |
| `src/config.py` | (opt) wrap secret fields in `SecretStr`, or note "never log `settings`" | product |
| `lab/harness.py` | `solve_grade_write` reads `getattr(solver, "trace_extras", None)`, passes to `build_record` | **neither hash** (additive) |
| `lab/trace.py` | `build_record(..., extras=None)` threads `trajectory`/`raw`/`latency_ms`/tokens (default-preserving) | **neither hash** (additive) |
| `lab/solvers.py` | + `AgentSolver` (`kind="agent"`, persistent `asyncio.Runner`, sets `self.trace_extras`); + inline `SUBMIT_ANSWER_TOOL` schema + module-level `lab_execute_tool` dispatcher | lab (swappable) |
| `lab/run.py` | + `--agent`: separate code path (build `[AgentSolver]`, print agent summary, **skip the `results["oracle"]` invariant block entirely**) | lab (swappable) |
| `tests/test_api/test_vote_tool.py` (NEW) | async handler: vote-time party for a SWITCHER + counts + rows + not-found + malformed-id | test |
| `tests/test_lab/test_agent_solver.py` (NEW) | **sync `def`**; mock `run_agentic_chat`; injectable client; assert mapping + no-prompt-leak + no live call | test |

**FROZEN-by-contract untouched:** `lab/scoring.py`, `lab/graders.py`, `validate_gold`, the
`TraceRecord` *field contract* (only additive optional fields used), the vocab in
`src/ingestion/vote_parsers.py`. `grading_contract_hash` + `content_hash` MUST stay unchanged
(verified by `test_hashes`). `harness.run`/`build_record` are extended **additively** per Decision 1.

## Dependency graph

```
Phase 0 (auth spike) ──gate(X|W)──> A1 (get_vote_event + get_bill_detail fix)
                                          │
                          A2 (submit_answer + lab dispatcher + model param) ── A3a (trace-capture seam)
                                          └──────────────┬───────────────────────────┘
                                                         A3b (AgentSolver) ── A4 (--agent entry) ── A5 (live smoke, manual)
```

---

## Phase 0 — backend auth spike (BLOCKING gate)

- [x] Scratchpad-only (NOT committed) script: `AsyncAnthropic(auth_token=settings.anthropic_auth_token)`, one `messages.create` with a single trivial tool forcing `tool_use`; assert ONLY on `stop_reason`/tool round-trip. **Never print/log/persist the token.**
- [x] **Gate: PASS → Option X.** OAuth-on-Messages-API works: `claude-haiku-4-5` returned `stop_reason=tool_use`; `claude-sonnet-4-6` returned 429 (authenticated, rate-limited — not a 401/403). Zero marginal cost via subscription. Option W not needed.
- [x] **Pinned model = `claude-sonnet-4-6`** (capability measurement). Note: sonnet 429s under throttle — pace the live n=10 smoke; the anthropic SDK auto-retries 429.

## Phase A1 — `get_vote_event` product tool + `get_bill_detail` fix

- [x] `get_vote_event` schema in `RESEARCH_TOOLS` (`src/llm/tools.py`): required string `vote_event_id`.
- [x] `_tool_get_vote_event(arguments, db, harness) -> str` in `src/api/chat.py`:
  - Wrap the WHOLE body in `try/except Exception` → `json.dumps({"error": "..."})` with a GENERIC message (no DB traceback / schema leak). Always return valid JSON (so `run_agentic_chat`'s `json.loads` summary step never raises).
  - Header via `select(VoteEvent).where(VoteEvent.id == eid)` (bound param); `None` → `{"error": f"Vote event '{eid}' not found."}`.
  - Per-member rows: async select `VoteRecord → Person`, **outer**-join `PersonPartySpan` on the half-open as-of predicate; return `(person_id, name, option, party|None)`. **If `vote_date IS NULL`, skip the span join entirely and return `party=None` for all** (don't rely on NULL-propagation). **Dedupe** any duplicate member rows from a >1-span voter (keep the bound consistent with gold; document that the gold excludes such events for party templates).
  - Mirrors `lab/templates._event_party_splits` as-of semantics EXACTLY (half-open, exclusive end), but surfaces ALL options + `party=None` rather than excluding — so on the events the party templates grade (every voter exactly one span) the tool's party is **identical** to gold.
  - JSON: `{vote_event_id, motion_text, result, chamber, vote_date, yes_count, no_count, other_count, records: [{person_id, name, option, party}]}`.
- [x] Register `"get_vote_event"` in `_TOOL_HANDLERS` (NOT `_HARNESS_REQUIRED_TOOLS`).
- [x] Fix `get_bill_detail`'s false "vote history" description (`tools.py`), pointing at `get_vote_event`.
- [x] **Acceptance** (`tests/test_api/test_vote_tool.py`, mock-session pattern from `test_policy_workspaces.py`): a SWITCHER returns **vote-time** party (not current `people.party`); stored counts + per-member rows present; a synthetic absent EVENT → clean `{"error"}`; a **malformed/type-mismatched** id → clean `{"error"}` (no traceback); **the realistic refusal shape** — a REAL event whose `records` simply DO NOT contain a given (synthetic) person id (this is how `vote_lookup` refusals actually work). Ruff + full suite green.

## Phase A2 — `submit_answer` + lab dispatcher + model pin

- [x] In `lab/solvers.py` (inline — no separate `lab_tools.py` for one template): `SUBMIT_ANSWER_TOOL` schema = `{answer: string (optional), refused: boolean (default false)}`. Description: "call exactly once to finish; set `refused=true` **iff the asked-about member is not present in the data you retrieved**; otherwise put the member's recorded vote in `answer`, copied **verbatim** from that member's `option` field in `get_vote_event` (a canonical token)."
- [x] Module-level `async def lab_execute_tool(tool_name, arguments, db, harness) -> str` (plain function, no factory): `submit_answer` → `json.dumps({"status": "recorded"})`; else delegate to `src.api.chat.execute_tool` (lazy import).
- [x] `src/services/chat_service.py`: add optional `model: str | None = None` to `run_agentic_chat` (default → `settings.summary_model`); backward-compatible. (Left `stream_agentic_chat`'s identical hardcode untouched — non-stream path only.)
- [x] **Acceptance:** `tests/test_lab/test_agent_seam.py::TestLabExecuteTool` — acks `submit_answer` + routes `get_vote_event` to `execute_tool`.

## Phase A3a — trace-capture seam (Decision 1, additive)

- [x] `lab/harness.py::solve_grade_write`: after `answer = solver.solve(inst)`, read `extras = getattr(solver, "trace_extras", None)` and pass `extras=extras` to `build_record`.
- [x] `lab/trace.py::build_record(..., extras=None)`: `extras = extras or {}`; set `trajectory`/`raw`/`latency_ms`/tokens/cost from `extras` (tokens/cost DEFERRED → None for Phase A). Deterministic solvers (no `trace_extras`) → unchanged defaults.
- [x] **Acceptance:** lab suite green (88, was 84 + 4); `test_hashes` confirms `grading_contract_hash` + `content_hash` UNMOVED; `test_agent_seam.py::TestBuildRecordExtras` asserts agent `extras` round-trip + deterministic defaults preserved.

## Phase A3b — `AgentSolver`

- [ ] `lab/solvers.py`: `AgentSolver` — `name="agent"`, `kind="agent"`, `policy={"backend","model","system_prompt_id"}` (strings only, **never the client/token**). Constructor takes an **injectable `client`** (defaults to `get_oauth_anthropic_client()` for X / the SDK harness for W) so the unit test passes a `Mock()` and never needs auth.
  - Hold **one persistent `asyncio.Runner`** for the solver's lifetime; `solve(inst)` = `self._runner.run(self._asolve(inst))` (NOT `asyncio.run` per call — the module-level pooled async engine binds connections to a loop; a fresh loop per instance crashes on instance #2). Close the runner at run end.
  - `_asolve(inst)`: build the user message from **`inst.prompt` ONLY** — never `inst.params` (holds the gold `person_id`) or `inst.gold`. Call the loop (X: `run_agentic_chat(system_prompt=<lab agent prompt>, messages=..., client=self.client, tools=[get_vote_event schema, SUBMIT_ANSWER_TOOL], model=<pinned>, execute_tool_fn=lab_execute_tool)`; W: the SDK equivalent). Measure wall-clock → `latency_ms`.
  - **Answer mapping** (read the LAST `submit_answer` from `all_tool_calls`): `refused=true` (authoritative) → `graders.REFUSAL`; `answer` present & `refused` falsy → pass the string THROUGH (no `OPTION_BUCKETS` coercion — a non-canonical answer correctly **format-fails** via `grade_exact`, scoring 0.0; the rationale is "honest format-fail," NOT "attempted-but-wrong"). The structured `refused` flag is authoritative — ignore an `answer` that literally equals the REFUSAL sentinel when `refused` is false (treat as malformed).
  - **Fallback** (no `submit_answer`, OR inconsistent payload [answer+refused / neither], OR loop hit `max_rounds`): return a fixed non-`REFUSAL`, non-canonical sentinel (e.g. `"__no_answer__"`) → guaranteed format-fail on BOTH arms (never undeserved refusal credit). Never crash.
  - Set `self.trace_extras = {"trajectory": all_tool_calls, "raw": final_text, "latency_ms": measured}`.
- [ ] **Acceptance** (`tests/test_lab/test_agent_solver.py`, **plain `def` — not `async`**, because `asyncio_mode=auto` would make the solver's own loop raise inside a running loop): MOCK `run_agentic_chat` (AsyncMock) for: (a) `submit_answer{answer:"yea"}`→`"yea"`; (b) `{refused:true}`→`REFUSAL`; (c) NO submit_answer → `"__no_answer__"`; (d) inconsistent → `"__no_answer__"`; (e) **on a REFUSAL instance, no-submit → `passed=False`** (no free refusal credit); (f) assert the messages passed to the mock contain **neither** the gold `person_id` **nor** `inst.gold`. Injected `Mock()` client → no live call, no auth.

## Phase A4 — agent run entry (`--agent`)

- [ ] `lab/run.py`: `--agent` flag takes a **separate code path** — build `solvers=[AgentSolver(...)]`, run via `harness.run`, print the agent's pass rate + mean score + per-instance pass/fail, and **skip the entire `results["oracle"]`/wrong/over-refuse invariant block** (those keys don't exist for an agent run → would `KeyError`). Default `--n 10` for agent runs. The deterministic path (no `--agent`) is unchanged and still asserts.
- [ ] **Acceptance:** `--agent` path unit-exercised with a mocked solver (no live call); deterministic invariants still run + pass without `--agent`.

## Phase A4b — duplicate-name noise floor (integrity)

- [ ] Read-only diagnostic (no gold/template change): over the sampled `vote_lookup` events, count cases where the chosen member's `name` is non-unique within the event. Post-hoc **annotate/exclude** any collided instance from the **reported** pass rate (trace-side filter, never a gold edit) so the headline number isn't corrupted by input ambiguity. Document residual as a Family-10 data-quality seed.

## Phase A5 — live smoke (MANUAL acceptance, not CI)

- [ ] Backend resolved (Phase 0) + Docker Postgres up: `uv run python -m lab.run --template vote_lookup --agent --n 10`. Confirm: loop runs end-to-end; agent calls `get_vote_event` then `submit_answer`; answers graded; a `solver_kind="agent"` JSONL trace is written **with non-empty `trajectory` + real `raw` prose + `latency_ms`**; refusal instances handled (agent refuses when the asked-about member is absent from the records). Record the observed pass rate (measurement; no target). Makes real API/SDK calls — NEVER a CI test.

---

## System-wide impact

- **Interaction graph:** `lab.run --agent` → `harness.run` (psycopg2 load + close) → solve loop → `AgentSolver.solve` → persistent `asyncio.Runner` → loop (X: `run_agentic_chat` / W: SDK) → per-tool `async_session_factory()` session → `_tool_get_vote_event` → `submit_answer` ack → `all_tool_calls` → answer map → frozen `grade()` → `solve_grade_write` reads `trace_extras` → `build_record(extras=...)` → `write_trace`.
- **Sync↔async + pool:** the lab is sync (psycopg2, closed before solving); the agent path is async on the module-level POOLED engine. **One persistent `Runner`** keeps every pooled asyncpg connection bound to a single loop across all N instances (a per-instance `asyncio.run` closes the loop and crashes instance #2).
- **Non-deterministic solver:** invariants apply ONLY to the 3 deterministic solvers; `--agent` is a separate, non-asserted path. `solver_kind="agent"` keeps live rollouts filterable from oracle rows in any training set.
- **Refusal (corrected):** `vote_lookup` refusals = a synthetic absent PERSON over a REAL event; the agent refuses because the member is absent from `records`, NOT because the tool errored. The not-found-EVENT branch is robustness for garbage event ids, not the refusal mechanism.
- **Error propagation:** `get_vote_event` never raises (full-body `try/except` → JSON error); the AgentSolver catches its own failures → `"__no_answer__"`, never crashing the run.
- **API surface parity:** `get_vote_event` is a real product tool — chat AND MCP agents (`src/mcp/server.py` auto-lists `RESEARCH_TOOLS`) gain vote competence; the `get_bill_detail` lie is removed.
- **Integration scenarios unit tests miss:** the live smoke (A5) is the only thing exercising real auth + tool loop; CI mocks the LLM (the docs/solutions MCP learnings note all 3 prior SDK bugs were live-only).

## Risks & mitigations

- **[was BLOCKING] Backend/auth.** Phase 0 spike → Option X, else blessed Option W (zero-cost, works today), else metered key. OAuth client via a named `deps.py` helper, env-backed, never hardcoded; spike never logs the token.
- **[was BLOCKING] Event-loop/pool crash.** Persistent `asyncio.Runner` (A3b).
- **Frozen-core trace contradiction.** Resolved by the additive seam (Decision 1) — moves neither hash; deterministic path unchanged (re-verified by `test_hashes` + the 84 tests).
- **Gold leak.** Messages built from `inst.prompt` only; test asserts no `person_id`/`gold` in the prompt.
- **Under-refusal cheat.** Fallback sentinel is non-`REFUSAL`/non-canonical → format-fail on both arms; tested on a refusal instance.
- **Format-gate reality.** A non-canonical answer format-fails (0.0), not 0.5 — tests assert format-fail; `submit_answer` instructs copying the verbatim `option` token.
- **Duplicate names.** Read-only diagnostic + post-hoc reported-rate exclusion (A4b); Family-10 seed.
- **Model default mismatch.** New `model` param pinned to a Claude id.
- **Phase-B party divergence.** The OUTER-join/`party=None` shape is safe for party-agnostic `vote_lookup`; Phase B party templates MUST gate on the same `COUNT(span)==1` eligibility before grading. Documented at the join.
- **Secrets.** Token only via settings/env; `policy`/`trace` store strings only (verified: trajectory = tool name+args+summary, no secrets); consider `SecretStr` so a stray `log(settings)` can't dump keys. Cost bounded: `--n 10`, `max_rounds=10`, manual-only.

## Out of scope (explicit)

- **Phase B:** the multi-event retrieval tool for window/member templates + widening to all 8.
- Threading real `usage`/`cost` end-to-end (tokens/cost stay `None`; `latency_ms` IS captured).
- Any grader/scoring/template/registry change; any `TraceRecord` field-contract change (only additive optional fields are populated).
- Productionizing the eval (scheduling/dashboards). If Phase 0 → Option Y were ever forced, re-review `bypassPermissions` + the all-10-tool exposure + a least-privilege MCP env allowlist.

## Sources & references

- Loop: `src/services/chat_service.py:87-189` (`run_agentic_chat`; only catches ValueError/LookupError/JSONDecodeError at :144, so a sentinel-exception early-break would be swallowed — read the LAST `submit_answer` from `all_tool_calls` instead), `:75-84` (per-tool session), `:420-481` (SDK/MCP path for Option W reference).
- Backend: `src/api/deps.py:44-97`; `src/llm/claude_sdk_adapter.py:113-148` (ignores `tools=`, hardcodes `end_turn`); `src/config.py` (`anthropic_auth_token` dead, `summary_model`=`gpt-4o-mini`); `src/database.py:6` (module-level POOLED async engine → the loop-binding hazard).
- Tools: `src/api/chat.py:413-448` + `_tool_get_bill_detail:122-190`; schema `src/llm/tools.py:40`.
- Models: `src/models/vote.py`, `person.py` (`party` current-only), `person_party_span.py` (half-open exclusive end).
- Gold to mirror: `lab/templates.py:527-553` (`_event_party_splits`), `:484-512` (`_party_eligible_events`, `HAVING COUNT(pps.id)<>1`), `:82-114` (vote_lookup gen + the person-absent refusal arm).
- Frozen seam: `lab/harness.py:94-104` (`solve_grade_write`), `lab/trace.py:139-170` (`build_record` hardcodes trajectory/raw — extended additively), `:35-51` (hash sets — `harness.py`/`trace.py` in NEITHER), `lab/scoring.py:54-57` (format gate + fabrication floor), `lab/graders.py:88-128`.
- Tests/mocks: `tests/test_api/test_policy_workspaces.py:640-652` (mock `run_agentic_chat` + AsyncMock session); `pyproject.toml` `asyncio_mode="auto"` (→ sync solver test).
- Learnings: `docs/solutions/architecture/mcp-server-research-tools.md` (permission_mode, history-poisoning, live-only SDK bugs); prior Family 1 plans + `docs/condorcet/2026-06-26-family1-corpus-shape.md`; scope `docs/scopes/2026-06-24-family1-harness-scope.md`.

## Panel resolutions (rev 2 traceability)

- **[B1] frozen-core trace contradiction** → Decision 1 additive seam (A3a). | **[B2] asyncio.run crash** → persistent `Runner` (A3b).
- **Refusal mis-described** → A1/A5 corrected (person-absent-from-real-event) + A1 test (e). | **Gold leak via params** → A3b prompt-only + test (f).
- **Fallback==REFUSAL cheat** → non-canonical sentinel + test (e). | **"attempted-but-wrong" wrong** → format-fail rationale + verbatim-option instruction.
- **Option W missing** → Decision 0 blessed fallback. | **OAuth client location/logging** → `deps.py` helper + spike no-log guard.
- **get_vote_event traceback leak** → full-body try/except + bound params + malformed-id test. | **Duplicate names** → A4b diagnostic.
- **--agent KeyError** → separate code path (A4). | **Sync test / injectable client** → A3b. | **vote_date NULL / dup rows** → A1 explicit handling.
- **Simplicity** → no `lab_tools.py`/factory (inline + plain `lab_execute_tool`); tokens/cost firmly deferred (latency only).
