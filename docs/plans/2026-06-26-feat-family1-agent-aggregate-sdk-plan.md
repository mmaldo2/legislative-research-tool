---
title: "feat: Family 1 agent slice 2 — aggregate answer shapes + Agent SDK backend"
type: feat
status: completed
date: 2026-06-26
revision: 2  # rev 2 after the 5-lens panel (4 integrity blockers + a simplification folded in)
---

# Family 1 agent slice 2 — aggregate templates + Option W (Agent SDK backend)

## Overview

Generalize the lab `AgentSolver` from a scalar-option answer to the **aggregate answer shapes**
(int / dict / set) the other event-keyed templates need, then add a second, **subscription-native
backend** (the Agent SDK, "Option W") so the agent can run on sonnet/opus without the Messages-API
rate wall. Then run the live agent on the **4 event-keyed aggregate templates** (`tally`,
`party_breakdown`, `party_defection`, `crossed_party`) — the reasoning-over-records tasks where the
difficulty lives (slice 1 proved lookup is trivial for even haiku).

`get_vote_event` already serves all 5 event-keyed templates → **no new tool**. The work: (1) a
shape-aware `submit_answer` + a grader-dispatched coercion in `_map_answer`, (2) the Agent SDK
backend. **Sequencing (blessed): generalize → validate on HAIKU (Option X, no rate wall) → build
Option W → run sonnet/opus.** Haiku validation is a checkpoint *before* the Option W work.

Frozen core is untouched — all of this lives in swappable `solvers.py`/`run.py` (NEITHER hash set);
`test_hashes` is the guardrail. Rev 2 commits the coercion/mapping to **exact predicates** (the panel
required this) and folds in 4 integrity fixes the deterministic invariants cannot catch.

## Blessed / locked decisions (do NOT re-open)

- **Shape-aware `submit_answer`** — per-template typed `submit_answer` input schemas (a lab-side
  `SUBMIT_SCHEMAS` registry keyed by `template_id`). Structures the **question** (field NAMES), never
  the answer **values** — leak-safe. Lives in swappable lab code (no hash impact).
- **`_map_answer` generalized + grader-dispatched** (see Resolved residual #1/#3 for the exact rules).
- **One general system prompt + the shape-aware `submit_answer` fields carry the output contract**
  (no per-template hint). No new grader mode.
- **Backend strategy on `AgentSolver`**: `backend ∈ {"messages-api" (Option X, default), "agent-sdk"
  (Option W)}`. Shared core (SUBMIT_SCHEMAS, `_map_answer`, `trace_extras` shape, diagnostics,
  refusal) is backend-agnostic; only loop-drive + capture differ.
- **Option W = in-process MCP tool server + CLI-subprocess model loop** (the SDK `query()` spawns the
  `claude` CLI; only the `@tool`s run in our process). Subscription creds via on-disk `claude login`.
- **Scope**: all 4 event-keyed aggregate templates; vote_lookup folds in (regression-safe). **Out of
  scope**: Phase B (multi-event window tool for closest/member_summary/pairwise).

### Simplification adopted (panel): no `AnswerSpec`/`assemble`/`task_hint`
Shape is a function of the **grader**, not the template — so there is ONE `coerce(grader, payload)`
(4 branches), not 5 per-template `assemble` closures. The registry is just
`SUBMIT_SCHEMAS: dict[template_id, dict]` + `GOLD_KEYS: dict[template_id, tuple]` (for `fields`). No
dataclass, no `task_hint`.

## Resolved residuals (EXACT predicates — committed, not prose)

**1. `_map_answer(tool_calls, *, grader, template_id)` — exhaustive, uniform mapping order.**
Answer fields in every `submit_schema` are **OPTIONAL** (not in `required`; only `refused` has a
default) so a bare `{refused: true}` is expressible (else the agent literally cannot refuse the
aggregate twins). `answer_present` is per-grader (below). Order:
   1. no `submit_answer` call → `NO_ANSWER`.
   2. `refused == true` AND `answer_present` → `NO_ANSWER` (inconsistent — keeps `test_inconsistent_both_is_fallback` green).
   3. `refused == true` (and not `answer_present`) → `graders.REFUSAL`.
   4. not refused AND `answer_present` → `coerce(grader, payload)` (may itself return `NO_ANSWER`).
   5. else → `NO_ANSWER`.
   `_map_answer` stays OUTSIDE the `_asolve` try (mapper bugs crash loudly); `coerce` is TOTAL.
   `answer_present` per grader: `exact` = non-empty non-`REFUSAL` str; `fields` = ≥1 of GOLD_KEYS
   present & non-None; `exact_int` = `count` present & non-None; `set_match` = `member_ids` present
   (any list, incl. empty — an explicit empty crossers set IS an answer, not a refusal).

**2. Task hint** — ONE general system prompt ("retrieve with get_vote_event, COMPUTE the answer the
question asks for, then call submit_answer EXACTLY ONCE with the structured fields; to REFUSE set
`refused=true` and do NOT fill the answer fields; never guess") + the per-template `submit_answer`
field descriptions (which restate the QUANTITY, never the METHOD) + `Instance.prompt`. The
vote-lookup-specific `_AGENT_SYSTEM_PROMPT` becomes this general one; `policy.system_prompt_id =
"lab_family1_v1"`.

**3. `coerce(grader, payload)` — one fn, grader-dispatched, TOTAL (any exception → `NO_ANSWER`).**
   Shared `_to_int(v) -> int | None`: `isinstance(v, bool)`→None; `int`→v; `float`→`int(v)` iff
   `math.isfinite(v) and v == int(v)` else None; `str`→`int(v.strip())` in try (so `"5"`→5,
   `"5.0"`/`"abc"`/`""`→None); else None.
   - `exact` → `payload["answer"]` passthrough str.
   - `exact_int` → `n = _to_int(payload.get("count"))`; `None` → `NO_ANSWER`; else `n`.
   - `fields` → build `{k: _to_int(payload.get(k)) if k in NUMERIC_FIELDS else str(payload.get(k))
     for k in GOLD_KEYS[template_id]}`; if a numeric field's `_to_int` is None, keep the **raw**
     `payload.get(k)` (a non-coercible field → still a dict with the gold key-set → grades
     attempted-but-wrong, NOT format-fail). Built from `GOLD_KEYS` so `answer.keys() == gold.keys()`
     always; `refused` NEVER included. (NUMERIC_FIELDS for tally = yea/nay/margin, result=str;
     breakdown = yea/nay.)
   - `set_match` → `mi = payload.get("member_ids")`; `if not isinstance(mi, list | tuple): NO_ANSWER`
     (a `str`/`dict` is iterable → would mis-grade — gate BEFORE the comprehension); else
     `[str(x) for x in mi]` (empty list OK).
   Both `exact_int` and the `fields` numeric path use the SAME `_to_int` (so a correct `12.0`/`"12"`
   doesn't false-fail). Deliberate asymmetry (comment it): a bare non-int for `exact_int` →
   `NO_ANSWER`; a non-coercible `fields` sub-value → raw → attempted-but-wrong.

**4. Option W loop / capture — corrected framing.** The model loop runs in the spawned **`claude`
   CLI subprocess** (prereq: `claude` on PATH + `claude login`-authed on the lab host — an explicit
   Phase 3 gate). Only the `@tool`s run in-process. The product's greenlet/`to_thread` dance exists
   to keep the Anthropic SDK's httpx off the SQLAlchemy greenlet thread; here the model HTTP is
   out-of-process, so THAT conflict can't occur — the real first-smoke unknowns are (a) anyio
   task-group + `anyio.open_process` cohabiting with the persistent `asyncio.Runner`, (b) the `@tool`
   asyncpg session on the Runner loop. Run `query()` on the Runner loop; if it corrupts, fall back to
   a dedicated loop/thread (note: query-loop and tool-loop are necessarily the SAME loop; a fallback
   NullPool/per-call engine must be disposed in `close()` too). **Build the SDK server INSIDE
   `_asolve_sdk`** (per-instance) so the `@tool` closures capture FRESH per-call lists (mirrors the
   Option-X `observations` local — no shared holders, no reset discipline). Factor each `@tool` body
   into a directly-callable async method (`self._sdk_get_vote_event`/`self._sdk_submit`) so the
   mocked test can drive them. The `get_vote_event` `@tool` routes through `lab_execute_tool("get_
   vote_event", args, db, harness=None)` (the SAME product-dispatch seam as Option X) and records a
   `{"tool":"get_vote_event","arguments","result"}` observation (BARE name); the `submit_answer`
   `@tool` records its args AND appends a `{"tool":"submit_answer",...}` observation (trajectory
   parity with Option X) and returns the ack. Build `_map_answer`'s `tool_calls` from the captured
   submit args. `raw` = the final text (`ResultMessage.result` / joined `TextBlock`s). Same
   try/except → `(NO_ANSWER, {trajectory, raw:_safe_err, latency_ms})`. Caps: `max_turns≈8`,
   `max_budget_usd≈1.0` (lower to ~0.50 for opus) — **per-rollout, not per-run**; `query()` spawns a
   subprocess per instance (≈13/template). Lazy SDK imports inside the driver.

**5. Option W hermeticity + tool-constraint (BENCHMARK-INTEGRITY GATE).** `bypassPermissions` + the
   CLI transport exposes the CLI's BUILT-IN tools (Bash/Read/Write/WebFetch) — a contamination
   vector (the agent could `psql`/read gold off disk/answer without retrieving). MUST: pin
   `disallowed_tools=[…built-ins…]` (or a permission mode that whitelists only `mcp__lab__*`),
   `setting_sources=[]` (no ambient `CLAUDE.md`/`.claude` config/MCP), an explicit neutral `cwd`, and
   **assert/pop `ANTHROPIC_API_KEY`** from the query env (else the in-process query silently bills the
   Messages API + hits the rate wall Option W exists to dodge). **Phase 3 EXIT GATE (first smoke):
   prove the agent CANNOT call any non-`lab` tool and inherits no ambient config** before any Option
   W pass rate is trusted. Record the hermetic settings in `policy`.

**6. Backend wiring + diagnostics.** `AgentSolver(backend="messages-api", ...)` default; `run.py
   --backend {messages-api,agent-sdk}` (default messages-api). `policy` records `backend`
   (`"messages-api"`/`"agent-sdk"` — confirm no DuckDB read-side filters on the old literal
   `"anthropic-oauth"`). Model default: X → `claude-sonnet-4-6` (pass `--model claude-haiku-4-5` for
   P2); W → `--model` sonnet/opus. Diagnostics: the `retrieved` flag → "any obs whose **BARE** tool
   name != `submit_answer`" (the SDK namespaces `mcp__lab__…`; compare the bare name or the guard
   silently disables on the SDK path); `run.py`'s missing-history default for `retrieved` →
   **False** (fail-closed). **NEW — trivial-constant baseline** (the data-integrity fix): in
   `_run_agent`, for the run's grader print the always-trivial floor — `exact_int`: share of
   answerable golds `== 0`; `set_match`: share `== ∅` — and the agent's answerable pass rate
   AGAINST it, so a 45% defection rate isn't read as 45% reasoning when ~35% is free. Pure count over
   `inst.gold`, no DB. `vote_lookup_name_collisions` stays vote_lookup-only.

**7. Tests (no live calls in CI).** `coerce` per-grader matrix (exact/exact_int/fields/set_match +
   refused + inconsistent + malformed: `nan`/`inf`/`None`/missing-key/`"5.0"`/`member_ids="p1"` →
   `NO_ANSWER`; integral-float + digit-str → int on BOTH exact_int and fields). **Key-set
   cross-consistency**: per `fields` template, `template.generate(...)` then assert
   `set(coerce-built dict) == set(a real gold)` (the actual frozen-spec coupling guard). Generalized
   `_map_answer` order (all 5 branches × shapes). Preserve the 10 `test_agent_solver.py` + 4
   `test_agent_seam.py` (vote_lookup unchanged; `_map_answer` signature ripple is mechanical). SDK
   backend test: mock `query()` to **`await` the real `@tool` methods** + yield a `submit_answer`
   call → assert typed mapping + observation capture (incl. the submit row) + `retrieved` (submit-only
   → False) + no gold leak + **tool-doc parity** (SDK `get_vote_event` def structurally == the
   `RESEARCH_TOOLS` entry). Gold-leak guard: messages AND every `submit_schema` field description
   contain no gold values and no METHOD tokens (`min(`, `minority`, `against the majority`). SYNC
   `def` where the solver spins its own loop. 2-line `ClaudeAgentOptions` field smoke before the
   Phase 3 build (wrong field name = constructor `TypeError`).

## Architecture (files touched — all NEITHER hash set)

| File | Change |
|---|---|
| `lab/solvers.py` | `SUBMIT_SCHEMAS` + `GOLD_KEYS` + `_to_int`/`coerce`; generalize `_map_answer` (grader-dispatched, uniform order); general system prompt; per-instance shape-aware `submit_answer`; the `backend` strategy + `_asolve_sdk` (in-process `@tool` server, integrity-locked options, ANTHROPIC_API_KEY guard, bare-name observations, trajectory parity); generalize the `retrieved` flag |
| `lab/run.py` | `--backend` flag; thread it + model; the trivial-constant baseline diagnostic; `retrieved` missing-history default → False |
| `tests/test_lab/test_answer_spec.py` (NEW) | `coerce` per-grader matrix + key-set cross-consistency |
| `tests/test_lab/test_agent_sdk_backend.py` (NEW) | mocked SDK driver (awaits real `@tool`s) + tool-doc parity + hermeticity-option assertions |
| `tests/test_lab/test_agent_solver.py` / `test_agent_seam.py` | keep green; extend for the generalized shapes |

**FROZEN untouched:** `lab/scoring.py`, `lab/graders.py`, `validate_gold` (already accepts dict/int/
set golds, `harness.py:74-91`), the `TraceRecord` field contract, `lab/templates.py` (the 4 templates'
gold/prompts unchanged). `grading_contract_hash` + `content_hash` MUST stay unmoved (`test_hashes`).

## Dependency graph

```
P1 generalize (SUBMIT_SCHEMAS + coerce + uniform refusal mapping + general prompt
               + retrieved-flag fix + trivial-constant baseline)            [Option X]
        │
   ── CHECKPOINT P2: HAIKU live across the 4 templates (read traces, baseline-relative difficulty) ──
        │   (off-ramp: if the haiku read is conclusive, P3/P4 MAY split to a follow-up slice)
        │
P3 Option W (claude-CLI prereq smoke → INTEGRITY EXIT GATE → in-process @tool server + SDK driver)
        │
   ── CHECKPOINT P4: sonnet/opus via Option W (capable-model measurement) ──
```

---

## Phase 1 — generalize the answer shapes (Option X)

- [x] `SUBMIT_SCHEMAS` (per-template, answer fields OPTIONAL, descriptions = QUANTITY not METHOD) + `GOLD_KEYS` + `_to_int` + `coerce` (exact predicates above; TOTAL).
- [x] Generalize `_map_answer(tool_calls, *, grader, template_id)` to the uniform 5-step order; keep it outside the `_asolve` try. vote_lookup spec reproduces the current string passthrough (preserves test #6 tool-set/model + tests #1–5).
- [x] Per-instance shape-aware `submit_answer` from `SUBMIT_SCHEMAS[inst.template_id]`; replace `_AGENT_SYSTEM_PROMPT` with the general prompt; `policy.system_prompt_id="lab_family1_v1"`.
- [x] Fix the `retrieved` flag (bare tool name, != submit_answer); `run.py` missing-history default → False.
- [x] `_run_agent` trivial-constant baseline (exact_int zero-share / set_match empty-share + pass-vs-floor).
- [x] **Acceptance:** `test_answer_spec.py` (coerce matrix + key-set cross-consistency); the 10+4 existing tests STILL green; `test_hashes` UNMOVED; full suite + ruff green.

## Phase 2 — HAIKU validation (CHECKPOINT, manual; not CI)

- [x] Per template `t ∈ {tally, party_breakdown, party_defection, crossed_party}`: `uv run python -m lab.run --template t --agent --model claude-haiku-4-5 --n 10`.
- [x] **Read traces** (trust bar): confirm retrieve→COMPUTE→submit-right-shape; check format-fail / agent-error / no-retrieval / **pass-vs-trivial-baseline**. Record per-template pass rate + difficulty read (tally near-trivial copy; breakdown moderate; defection/crossed the hard ones). STOP for review. **Off-ramp decision:** if conclusive, P3/P4 may become a follow-up slice.

## Phase 3 — Option W (Agent SDK backend)

- [x] Pre-flight smoke: `claude` CLI on PATH + `claude login`-authed; a 2-line `ClaudeAgentOptions(model, allowed_tools, mcp_servers, permission_mode, setting_sources, disallowed_tools, cwd, max_turns, max_budget_usd)` construct (confirm field names + the `allowed_tools` `mcp__lab__*` vs bare naming).
- [x] In-process `@tool`s (built INSIDE `_asolve_sdk`, fresh per-instance closures): `get_vote_event` (def sourced from `RESEARCH_TOOLS['get_vote_event']`; routed through `lab_execute_tool`; records bare-name observation) + `submit_answer` (schema from `SUBMIT_SCHEMAS`; records args + a submit observation; returns the ack). `create_sdk_mcp_server(name="lab", tools=[...])`.
- [x] `_asolve_sdk`: integrity-locked `ClaudeAgentOptions` (disallowed built-ins, `setting_sources=[]`, neutral `cwd`, pop `ANTHROPIC_API_KEY`, caps, general system_prompt); `query()` on the persistent Runner loop; iterate stream for `raw` + `ResultMessage`; build `_map_answer` input from captured submit args; same `trace_extras` + NO_ANSWER resilience + `_safe_err`.
- [x] `AgentSolver(backend=...)` strategy; `run.py --backend`; `policy["backend"]`.
- [x] **INTEGRITY EXIT GATE (first live smoke):** prove the agent (a) cannot call any non-`lab` tool, (b) inherits no ambient config, (c) uses subscription creds (not the API key). Do NOT trust any W pass rate until this passes.
- [x] **Acceptance:** `test_agent_sdk_backend.py` (mock `query()` that AWAITS the real `@tool` methods; typed mapping + observation/submit capture + retrieved=False on submit-only + no gold leak + tool-doc parity); messages-api path unchanged; ruff + suite green.

## Phase 4 — sonnet/opus via Option W (CHECKPOINT, manual; not CI)

- [x] After the P3 integrity gate passes: `uv run python -m lab.run --template t --agent --backend agent-sdk --model claude-sonnet-4-6 --n 10` per template (then optionally opus, `max_budget_usd≈0.5`). Confirm no rate wall, tools constrained, traces capture observations + structured answer + latency. Read traces; record capable-model pass rates vs the haiku baseline AND the trivial-constant floor. STOP for review.

---

## System-wide impact

- **Interaction graph:** `lab.run --agent --backend X|W` → `harness.run` → `AgentSolver.solve` (persistent Runner) → `_asolve` (X: `run_agentic_chat`) / `_asolve_sdk` (W: `query()` on the Runner loop → in-process `@tool`s → `lab_execute_tool` → product `_tool_get_vote_event`) → `_map_answer(grader)` → frozen `grade()` → `solve_grade_write` reads `trace_extras` → `build_record` → JSONL.
- **Backend parity (the measurement-validity crux):** both backends must present the agent the SAME `get_vote_event`/`submit_answer` name+description+schema (sourced from `RESEARCH_TOOLS`/`SUBMIT_SCHEMAS`), route through the SAME `lab_execute_tool`, and emit the SAME `trajectory` shape — else Phase-4 vs Phase-2 numbers aren't comparable. Note the round-cap asymmetry (X `MAX_TOOL_ROUNDS=10` vs W `max_turns≈8`) when comparing.
- **Sync↔async:** both run on the ONE persistent `asyncio.Runner` loop (asyncpg pool stays loop-consistent). The model HTTP is out-of-process (CLI subprocess) so the product's greenlet conflict doesn't apply; the real unknown is anyio+subprocess+`@tool`-asyncpg on the Runner loop (first-smoke validated; thread fallback documented).
- **Frozen core:** no grader/template/gold/scoring change; `solver_kind="agent"` + `policy.backend` keep rollouts filterable + backend-labeled; hashes unmoved.

## Risks & mitigations

- **[BENCHMARK-INTEGRITY] SDK built-in tools + ambient config (Option W).** Mitigated by `disallowed_tools`/whitelist + `setting_sources=[]` + neutral `cwd` + the Phase 3 exit gate. Until proven, no W number is trusted.
- **[FAIRNESS] Defection/crossed base-rate false-pass.** Mitigated by the trivial-constant baseline diagnostic (read every number against the always-0/∅ floor). The retrieve-then-guess case is still not fully separable (the per-template cross-check stays deferred — say so in the trace read).
- **`ANTHROPIC_API_KEY` ambient.** Popped/asserted in the driver (fail loud).
- **`claude` CLI prereq.** Explicit Phase 3 pre-flight; absence fails the gate, not mid-run.
- **anyio/Runner cohabitation (greenlet).** Validate first smoke; dedicated-loop/thread fallback (dispose any fallback engine in `close()`).
- **Coercion false-fail/false-pass.** Exact predicates + the shared `_to_int` + the key-set cross-test; pass-through discipline preserved (`3.7`→reject, never round).
- **Cost (live W).** `max_turns` + per-rollout `max_budget_usd` (≈0.5 opus); eyeball the first opus rollout's tokens before all 4 templates; the agent-error diagnostic catches throttles.
- **Slice-1 regression.** vote_lookup folds in; the 10+4 tests + test #6 are the guard. (Note: swapping vote_lookup's prompt to the general one re-baselines it vs slice 1 — `system_prompt_id` labels it; don't compare slice-1/slice-2 vote_lookup as same-prompt.)

## Out of scope

Phase B (multi-event window tool for `closest_by_margin`/`member_summary`/`pairwise_agreement`); the
defection/crossed per-template cross-check diagnostic; threading `response.usage`/cost; any
frozen-core / grader / template / gold change.

## Sources & references

- Graders (frozen, confirmed): `lab/graders.py` — `grade_fields:60-67` (exact gold keys; `_match_field` dispatches on gold type — int via `grade_exact_int`), `grade_set_match:70-76` (a LIST passes; a `str`/`dict` iterates → must be gated), `grade_exact_int:41-44` (real int; bool excluded), `_format_valid:93-109` (shape gate; `NO_ANSWER`/non-int str format-fails). `validate_gold` accepts dict/int/set: `harness.py:74-91`.
- Templates' gold/grader/prompt (unchanged): `lab/templates.py` — tally `:150-155` `{yea,nay,margin,result}` `fields`; party_breakdown `:582,612` `{yea,nay}` `fields`; party_defection `:676` bare int `exact_int`; crossed_party `:736` set `set_match`. Aggregate refusal twins = synthetic nonexistent EVENT → `_tool_get_vote_event` `{"error":…}` (`chat.py:211-212`).
- Current agent seams: `lab/solvers.py` — `_map_answer:153-172` (string-only; the inconsistent-before-refused order at `:166-172`), `SUBMIT_ANSWER_TOOL:85-107` (string-only), `_AGENT_SYSTEM_PROMPT:143-150` (vote-lookup-specific), `AgentSolver._asolve/_record:232-274`, persistent Runner `:212-217`, `policy.backend="anthropic-oauth":200`, `close` `engine.dispose():282-284`.
- Backend parity / dispatch: `src/llm/tools.py:58-65` (`get_vote_event` product description the SDK must mirror), `src/api/chat.py` (`execute_tool:507-519` thin dispatch; `_tool_get_vote_event:196-257` full roster), `lab/solvers.py:110-124` (`lab_execute_tool` — the shared seam).
- Agent SDK (probed): `claude_agent_sdk.tool`/`create_sdk_mcp_server` (`__init__.py:169,310`; `@tool` fn → `{"content":[{"type":"text","text":…}]}`; `input_schema` accepts a full JSON-schema dict), `query()` → async iterator (`AssistantMessage`/`ToolUseBlock`/`TextBlock`/`ResultMessage`); `ClaudeAgentOptions` fields incl. `model/allowed_tools/disallowed_tools/mcp_servers/permission_mode/setting_sources/cwd/max_turns/max_budget_usd` (`types.py`). CLI-subprocess transport: `_internal/client.py:127`; existing pattern `src/services/chat_service.py:422-487` (per-`query()` new loop + `to_thread`).
- Diagnostics: `lab/run.py::_run_agent` (format-fail/agent-error/no-retrieval, `:120-122`; missing-history fail-open `:121`); `vote_lookup_name_collisions` guarded.
- Learnings: `docs/solutions/architecture/mcp-server-research-tools.md` (permission-gate applies in-process; `bypassPermissions` is the fix BUT exposes built-ins → the integrity gate); slice-1 plan `docs/plans/2026-06-26-feat-family1-live-agent-vote-lookup-plan.md` (trace seam, persistent-Runner pool fix, Option W framing); corpus shape `docs/condorcet/2026-06-26-family1-corpus-shape.md` (the defection ~0.35 zero-fraction that motivates the baseline).

## Panel resolutions (rev 2 traceability)

- **[BLOCKER] defection/crossed base-rate false-pass** → trivial-constant baseline diagnostic (res #6, P1). | **[BLOCKER] refusal-mapping contradiction** → uniform 5-step order + optional answer fields (res #1). | **[BLOCKER] fields key-set** → build from GOLD_KEYS, exclude refused, + cross-consistency test (res #3/#7). | **[BLOCKER] SDK built-in-tool contamination** → disallowed_tools/whitelist + setting_sources=[] + integrity exit gate (res #5).
- **[MAJOR] "in-process" misnomer + claude-CLI prereq + greenlet mis-aim** → res #4 reframed. | **tool-doc parity** → source @tool defs from RESEARCH_TOOLS/SUBMIT_SCHEMAS + parity test. | **ANTHROPIC_API_KEY guard** → pop in driver. | **trajectory parity + bare-name retrieved** → submit @tool appends an obs; bare names. | **mocked test must invoke @tools** → directly-callable methods the fake awaits. | **total assemble** → `coerce` try/except + nan/inf/None tests. | **str member_ids** → isinstance gate. | **assemble→coerce collapse** → adopted (drop AnswerSpec/task_hint).
- **[MINOR] _to_int exact predicate / shared int-coercion / lazy SDK imports / per-instance server build / field-description method-leak / per-rollout cost+subprocess note / round-cap asymmetry** → all folded above.
