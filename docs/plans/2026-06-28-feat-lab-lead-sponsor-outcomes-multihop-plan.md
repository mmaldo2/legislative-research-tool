---
title: "feat(lab): lead-sponsor vote-outcomes template (Family 2, long-trajectory multi-hop, SCREEN-GATED)"
type: feat
status: active
date: 2026-06-28
origin: docs/scopes/2026-06-28-member-sponsorship-outcomes-multihop-scope.md
---

# feat(lab): lead-sponsor vote-outcomes (long-trajectory multi-hop, screen-gated)

## Overview
A new auto-graded benchmark template plus one new product tool, built to test whether a
**long sequential tool-loop** (orchestrate ~24 `get_bill_votes` calls over a member's sponsored
bills, drop nothing, return the exact subset) **defeats the frontier** (sonnet), not just haiku.
The covoting result (haiku 0/8 -> sonnet 8/8, sonnet ceilings the 2-call-then-compute join) proved
deepening the join families buys haiku-level separation only; the untested frontier shape is the
long trajectory. **Frontier-hardness is UNPROVEN -> this slice is HARD-GATED on a cheap haiku+sonnet
screen before any frozen-suite investment** (per [[feedback_lab_find_hard_families]]).

Task: *"Member X primarily sponsored bills in Congress 110. Of those, which received at least one
roll-call vote? List the bill_ids (empty list if none)."* gold = the SET of X's primary-sponsored
bills with >=1 `vote_event`; grader **`set_match`** (no new grader). The agent calls
`get_member_sponsorships(person_id, 110)` -> ~24 bills (NOT pre-joined to votes), then loops
`get_bill_votes(bill_id)` per bill, collecting the ~4 with a roll call.

## Problem Statement / Motivation
- The lab's discrimination signal has plateaued at the haiku<sonnet boundary on the join families
  (1/2/6). We need a task type hard for **sonnet** for both eval discrimination and RLVR signal.
- Moat is ~dead on public federal data (3 findings); optimize **discrimination + RLVR**, not moat
  ([[project_condorcet_build_backlog]], [[project_condorcet_eval_philosophy]]).
- The honest prior is a coin-flip: a careful frontier model may well loop 24 calls flawlessly and
  ace this like covoting. **The cheap screen exists precisely so we do not over-invest if it does.**

## Proposed Solution
- **One new read-only product tool** `get_member_sponsorships(person_id, congress)` that returns a
  member's PRIMARY-sponsored bills (`bill_id` + `identifier`), **NOT pre-joined to votes/status**
  (pre-joining collapses the loop = the answer-in-tool trap). Mirrors `_tool_get_bill_cosponsors`
  exactly, in the reverse direction (bills-by-member rather than cosponsors-by-bill).
- **One new frozen template** `family2.lead_sponsor_outcomes` (`set_match`), mirroring
  `family6.covoting_disagreement`'s structure (seeded selection, set gold, twins, drift guard).
- **Build is phased with a HARD GATE between Phase 2 and Phase 3** (the screen).

### Key design decisions (resolving the scope's Open Questions)
1. **Hand the agent the `person_id` directly** (+ display name for readability); tools =
   `[get_member_sponsorships, get_bill_votes]`. NO `find_people`. Rationale: the LOOP is the test,
   not name resolution; handing the id isolates the loop as the sole difficulty and sidesteps
   historical-name-ambiguity noise (Congress 110 has cross-congress name collisions). The loop is
   already the long trajectory (~24 calls) -- adding `find_people` would add one upfront call, not
   lengthen the loop, so we lose nothing on the frontier-hardness thesis. (Alternative B -- name +
   `find_people`, the covoting precedent -- is noted but rejected for the ambiguity risk.)
2. **Freeze Congress 110** (oldest/settled historical data; will never change). 119 has 0 primary
   sponsors; 110 has 17k primary sponsorships, 552 members with >=1 primary-sponsored bill,
   334 in the 15-50 band, |gold| median 4.
3. **Screen design**: haiku + sonnet, `--backend agent-sdk`, `--n 8 --seed 42`, on the
   natural-answerable subset, sampled from the **upper band (sponsored 30-50)** for the longest
   loops = best shot at exposing a gradient. Go/no-go bar below.
4. **Loop length without answer-biasing**: select members by primary-sponsored COUNT only
   (answer-independent). Each selected member loops their full 15-50 bills regardless of |gold|, so
   filtering suite composition by |gold| leaks no loop-length signal and lets no shortcut.

## Technical Approach

### New tool: `get_member_sponsorships` (mirror of `get_bill_cosponsors`, reverse direction)
`src/api/chat.py` -- add alongside `_tool_get_bill_cosponsors` (310-345). Pseudocode:

```python
# src/api/chat.py
async def _tool_get_member_sponsorships(
    arguments: dict[str, Any], db: AsyncSession, harness: LLMHarness
) -> str:
    """The bills a member PRIMARY-sponsored in a congress (RAW bill rows, NOT pre-joined to
    votes/status -- the agent loops get_bill_votes over them itself). One index-backed query on
    sponsorships.person_id filtered to classification='primary' and the congress, DISTINCT-ed.
    Guarded so a bad id never leaks a traceback. A real member with no primary bills in the
    congress returns an empty list; a nonexistent person returns a clean not-found error (the
    distinction is the agent's refusal signal)."""
    person_id = arguments.get("person_id", "")
    congress = arguments.get("congress", "")
    try:
        stmt = (
            select(Bill.id, Bill.identifier)
            .join(Sponsorship, Sponsorship.bill_id == Bill.id)
            .join(LegislativeSession, LegislativeSession.id == Bill.session_id)
            .where(
                Sponsorship.person_id == person_id,
                Sponsorship.classification == "primary",
                LegislativeSession.identifier == congress,
            )
            .distinct()
            .order_by(Bill.id)
        )
        rows = (await db.execute(stmt)).all()
        if not rows:
            # Only on empty do we pay the existence check: a missing person is the refusal basis;
            # a real member with no primary bills in the congress is a distinct (empty-list) answer.
            exists = (await db.execute(select(Person.id).where(Person.id == person_id))).first()
            if exists is None:
                return json.dumps({"error": f"Person '{person_id}' not found."})
        bills = [{"bill_id": bid, "identifier": ident} for (bid, ident) in rows]
        return json.dumps(
            {"person_id": person_id, "congress": congress, "bills": bills, "count": len(bills)}
        )
    except Exception:
        logger.exception(
            "get_member_sponsorships failed for person_id=%r congress=%r", person_id, congress
        )
        return json.dumps({"error": "Failed to retrieve the member sponsorships."})
```

- Register in `_TOOL_HANDLERS` (chat.py:713-730), NOT `_HARNESS_REQUIRED_TOOLS` (pure DB).
- `src/llm/tools.py` `RESEARCH_TOOLS`: mirror the `get_bill_cosponsors` schema but with two required
  params:
```python
{
    "name": "get_member_sponsorships",
    "description": (
        "List the bills a member PRIMARY-sponsored (authored) in a given congress, by their "
        "person_id: one row per bill with its bill_id and identifier. These are the bills the "
        "member led -- NOT cosponsored, and NOT pre-filtered by whether they got a vote. An "
        "empty list means the member primary-sponsored no bills in that congress; an error means "
        "no such person exists."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "person_id": {"type": "string", "description": "The internal person ID."},
            "congress": {"type": "string", "description": "The congress number, e.g. '110'."},
        },
        "required": ["person_id", "congress"],
    },
},
```

**Why `get_bill_votes(bill_id)` non-empty == the gold predicate (drift safety):** `_tool_get_bill_votes`
queries `vote_events WHERE bill_id = ?` and returns `roll_calls`; non-empty ⟺ `>=1 vote_event` for
the bill -- exactly the gold's `EXISTS vote_events` clause. Confirmed verbatim in research.

### New template: `family2.lead_sponsor_outcomes` (mirror `generate_covoting_disagreement`)
`lab/templates.py`. Constant + prompt + generator + registry entry.

```python
TEMPLATE_LEAD_SPONSOR_OUTCOMES = "family2.lead_sponsor_outcomes"
_LEAD_SPONSOR_CONGRESS = "110"
_LEAD_SPONSOR_BAND = (15, 50)        # answer-INDEPENDENT loop-length band (full frozen suite)
_LEAD_SPONSOR_SCREEN_BAND = (30, 50) # longest loops -> best shot at a gradient (screen only)

def _lead_sponsor_prompt(name: str, person_id: str, congress: str) -> str:
    """One prompt shape, shared by answerable + empty + refusal twins (the agent cannot tell them
    apart by phrasing -- only by verifying the data)."""
    return (
        f"Member {name} (internal person_id {person_id}) primarily sponsored bills in Congress "
        f"{congress}. Of those bills, which ones received at least one roll-call vote? List the "
        f"bill_ids (an empty list if none)."
    )

def generate_lead_sponsor_outcomes(conn, n, seed, precomputed, *, band=_LEAD_SPONSOR_BAND):
    # 1. selection (answer-independent): members with primary-sponsored COUNT in `band` in 110.
    #    SELECT sp.person_id, p.name, COUNT(DISTINCT sp.bill_id) nbills
    #    FROM sponsorships sp JOIN bills b ON b.id=sp.bill_id
    #      JOIN sessions s ON s.id=b.session_id JOIN people p ON p.id=sp.person_id
    #    WHERE sp.classification='primary' AND s.identifier='110'
    #    GROUP BY sp.person_id, p.name HAVING COUNT(DISTINCT sp.bill_id) BETWEEN band[0] AND band[1]
    # 2. sample(candidate_person_ids, n, seed)  (same deterministic helper covoting uses)
    # 3. per member, gold = primary-sponsored bills with >=1 vote_event:
    #    SELECT DISTINCT b.id FROM sponsorships sp JOIN bills b ON b.id=sp.bill_id
    #      JOIN sessions s ON s.id=b.session_id
    #    WHERE sp.person_id=%s AND sp.classification='primary' AND s.identifier='110'
    #      AND EXISTS (SELECT 1 FROM vote_events ve WHERE ve.bill_id=b.id)
    #    gold = {r[0]}  (a set of bill_id strings; MAY be empty -> natural answerable-empty member)
    # 4. emit Instance(template_id=TEMPLATE_LEAD_SPONSOR_OUTCOMES, grader="set_match",
    #       is_refusal=False, params={person_id, congress:'110', nbills, kind:"answerable"},
    #       prompt=_lead_sponsor_prompt(name, person_id, '110'), gold=gold)
    # --- Phase 3 only: twins ---
    #  - answerable-EMPTY twin: pin one member in-band with |gold|==0 (sponsored 15-50, none voted)
    #       -> gold=set(), is_refusal=False, kind="empty". (Natural; ~10% of the band already are.)
    #  - refusal twin: a SYNTHETIC person_id absent from people (assert SELECT 1 FROM people WHERE
    #       id=%s is None) -> _lead_sponsor_refusal(...): gold=REFUSAL, grader="refusal_correct",
    #       is_refusal=True, refusal_reason="member_not_in_data". get_member_sponsorships errors on
    #       it -> agent REFUSES. (NO find_people in the tool list -> no other recourse.)
    # emit-assert: inst.is_refusal == (inst.gold == REFUSAL) for every instance.
```

Register in `TEMPLATE_REGISTRY` (templates.py:1448, next to covoting at 1490):
```python
"lead_sponsor_outcomes": SimpleNamespace(
    name="lead_sponsor_outcomes",
    template_id=TEMPLATE_LEAD_SPONSOR_OUTCOMES,
    generate=generate_lead_sponsor_outcomes,
),
```
`precomputed` is accepted but UNUSED (the generator reads its own selection/gold SQL; gold depends
only on the member's own sponsorships + the bills' vote_events -- read identically by the gold SQL
and the two tools -> no roster-COUNT invariant, no complete-events gate, mirroring covoting).

### Solver seam (`lab/solvers.py` -- in NEITHER hash)
```python
# SUBMIT_SCHEMAS (~212):
"family2.lead_sponsor_outcomes": {
    "bill_ids": {
        "type": "array",
        "items": {"type": "string"},
        "description": "The bill_ids of the member's primary-sponsored bills that received at "
        "least one roll-call vote, as a list of strings (an empty list if none).",
    },
    **_REFUSED_FIELD,
},
# SET_MATCH_FIELD (~225):
"family2.lead_sponsor_outcomes": "bill_ids",
# TEMPLATE_TOOLS (~258): a NEW tool list (not _MEMBER_TOOLS):
"family2.lead_sponsor_outcomes": ["get_member_sponsorships", "get_bill_votes"],
```
`SqlOracleSolver/WrongBaselineSolver/OverRefuseSolver` then work automatically (set gold ->
`set(gold) | {"NX-wrong"}` for the wrong baseline; REFUSAL for over-refuse).

### The ∅-vs-refuse discipline (the covoting gold-bug lesson, applied)
covoting's cross-body twin was wrongly `gold=REFUSAL` when `[]` was correct -- caught only by reading
a trace ([[project_condorcet_covoting_discrimination_pending]]). Here the partition is clean and
distinguished by the tool's signal:
- **answerable-EMPTY** (real member, 15-50 primary bills, 0 voted): tool returns a non-empty bill
  list -> agent loops -> finds none -> returns `[]`. `gold=set()`, `is_refusal=False`.
- **refusal** (synthetic nonexistent person_id): tool returns a not-found ERROR -> agent REFUSES.
  `gold=REFUSAL`, `is_refusal=True`.
- The two never overlap: answerable-empty members have 15-50 sponsorships (list result), the refusal
  uses a person absent from `people` (error result). We do NOT select "real member, 0 sponsorships".

## The SCREEN GATE (mandatory, between Phase 2 and Phase 3)
Run after the tool (Phase 1) + minimal generator + solver seam (Phase 2). From repo root:
```
PYTHONPATH=. uv run python -m lab.run --agent --template lead_sponsor_outcomes \
    --model <M> --backend agent-sdk --n 8 --seed 42
```
for `M in claude-haiku-4-5 claude-sonnet-4-6` (the SCREEN samples the **30-50 upper band**).
**Use `--backend agent-sdk` -- NOT `messages-api` (it rate-walls sonnet/opus); agent-sdk is
subscription-native, no wall** ([[project_condorcet_covoting_discrimination_pending]]).

Compute pass rate on the natural-answerable (`kind=="answerable"`, |gold|>=1) subset. Read 2-3
traces to confirm any failure is real loop-dropping (omitted bills), not a tool/format artifact.

**Go/no-go bar (set_match is all-or-nothing):**
| sonnet natural-answerable | verdict |
|---|---|
| **<= 5/8** (drops bills on the long loop) | **GRADIENT -> proceed to Phase 3** (finish frozen suite; optionally run opus to confirm sonnet<opus). |
| **>= 7/8** (effectively ceilings it) | **STOP the slice.** Record the negative result; reassess. Frontier-hardness needs infra -> Family 8. |
| **6/8** (borderline) | Read all traces; add longer-loop instances (band 40-50) and re-screen before deciding. |

A haiku<sonnet gap is expected regardless (haiku will drop bills); the GATE is whether **sonnet**
struggles. If sonnet aces, the long-loop shape is NOT frontier-hard and we do not build the suite.

## Implementation Phases

### Phase 1: The tool (STOP for review) -- DONE
- [x] `_tool_get_member_sponsorships` in `src/api/chat.py` (mirror `_tool_get_bill_cosponsors`;
      returns ONLY `bill_id` per PR-3).
- [x] Register in `_TOOL_HANDLERS` (not `_HARNESS_REQUIRED_TOOLS`).
- [x] `get_member_sponsorships` def in `src/llm/tools.py` `RESEARCH_TOOLS`.
- [x] Gate edit (the ONLY one needed): `tests/test_mcp/test_server.py` -- added
      `"get_member_sponsorships"` to `EXPECTED_TOOLS` and both `== 16` -> `== 17`. (conftest
      `REQUIRED_COLUMNS` and `test_schema_columns` `_MODELS` already cover `sponsorships`/
      `Sponsorship` from PR #43 -- NO new table -> no change. Confirmed.)
- [x] Tool tests in `tests/test_api/test_provenance_tools.py` (PR-10: mirror the cosponsor tests):
      returns primary bills (bill_id only); EXCLUDES cosponsor (real-DB test); congress-scoped
      (different congress -> empty); nonexistent person -> error; hermetic DB-error guard
      (2-mock not-found via `side_effect=[empty, none]`; no traceback leak).
- [x] Full suite + ruff green (888 passed, 32 skipped = the cross-loop requires_pg pattern; the
      new requires_pg test passes in isolation). Commit. **STOP -- surface summary.**
- Hash impact: **both hashes UNMOVED** (no `templates.py` change this phase). Confirmed.

### Phase 2: Minimal generator + solver seam + THE SCREEN (HARD GATE) -- DONE, GATE = STOP
- [x] Added `TEMPLATE_LEAD_SPONSOR_OUTCOMES`, `_lead_sponsor_prompt`, `generate_lead_sponsor_outcomes`
      (screen config: band 30-50, |gold|>=1, answerable-only), registry entry, to `lab/templates.py`.
- [x] Solver seam in `lab/solvers.py` (SUBMIT_SCHEMAS, SET_MATCH_FIELD, TEMPLATE_TOOLS) + PR-1
      `--max-turns`/`--max-budget-usd` passthrough in `lab/run.py`.
- [x] ruff clean; full suite green (888 passed); deterministic invariants pass (oracle 8/8, wrong
      0/8, over-refuse 0/8).
- [x] Ran the screen (haiku, `--backend agent-sdk`, n=12 seed=42, `--max-turns 60`, 30-50 band).
- [x] **GATE = STOP (NEGATIVE, trace-verified 2026-06-29).** haiku **12/12 exact** (smoke 3/3),
      genuine 30-45-bill loops (get_bill_votes calls == nbills), all SDK `success` (no truncation),
      symmetric-diff = 0 on every pass (not off-by-one), 0 no-retrieval passes. The WEAKER model aces
      with zero artifacts -> sonnet (>= haiku) cannot struggle -> **sonnet NOT run** (cheap-first; a
      foregone conclusion). The long independent-tool-loop is NOT frontier-hard. See
      [[project_condorcet_longloop_negative]] (the refined principle: the lever is in-context
      computation over a large set, NOT call count).
- Hash impact: `content_hash` MOVED (templates.py); `grading_contract_hash` UNMOVED (no grader);
  `solvers.py` in neither hash.

### Phase 3: NOT BUILT (gate was negative)
Per the gate, the frozen suite (twins, frozen tests, drift guard, opus confirm) was NOT built --
the slice's premise (long-loop frontier-hardness) is disproven. Disposition is open (keep the tool +
run.py harness improvement; revert vs keep the screened-negative template). Original Phase-3 spec
retained below for the record.
- [ ] Add the twins to the generator: answerable-EMPTY (pinned in-band |gold|==0) + refusal
      (synthetic absent person_id), with the emit-assert binding `is_refusal == (gold == REFUSAL)`.
      Widen the frozen suite to the full 15-50 band.
- [ ] Frozen tests in `tests/test_lab/test_lead_sponsor_outcomes.py` (mirror
      `test_covoting_disagreement.py`):
  - `requires_pg` gold predicate: each gold bill is primary-sponsored by X in 110 AND has >=1
    vote_event; leak-safe (prompt never names a gold bill_id).
  - `requires_pg` **drift guard** (async, mirror `test_gold_equals_two_tool_diff`):
    `gold == {bill for bill in get_member_sponsorships(X, '110') if get_bill_votes(bill) non-empty}`
    -- equality, both read the same rows; best-effort skip on DB-down, FAIL on real drift.
  - `requires_pg` twins: empty -> `gold==set() and not is_refusal`; refusal -> `gold==REFUSAL and
    is_refusal and grader=="refusal_correct"` and the synthetic id matches no `people` row.
  - `requires_pg` deterministic invariants: oracle PASS, wrong-baseline FAIL, over-refuse FAIL on
    every answerable (incl. the [] gold).
- [ ] (Optional) opus confirm run, to characterize sonnet<opus on the gradient.
- [ ] Full suite + ruff green; `test_hashes.py` SPLIT still holds (grading_contract_hash UNMOVED).
- [ ] PR per global commit-push-pr: if `CHANGELOG.md` exists, add an `[Unreleased]` entry; if
      `VERSION` exists, evaluate a minor bump (new feature). `gh pr merge --merge --delete-branch`.

## Acceptance Criteria
- [ ] `get_member_sponsorships` returns ONLY primary-sponsored bills for the congress; distinguishes
      nonexistent person (error) from real-member-no-bills (empty list); no traceback leak.
- [ ] Template runs end-to-end under `lab.run --agent ... --backend agent-sdk` by end of Phase 2.
- [ ] The screen is executed with `--backend agent-sdk` and the verdict recorded against the bar.
- [ ] If gate-positive: frozen suite green, drift guard passes, `grading_contract_hash` UNMOVED,
      `content_hash` moved, `test_hashes.py` split holds.
- [ ] If gate-negative: NO frozen suite built; negative result + traces recorded in memory; slice
      closed with a reassessment note (-> Family 8 infra).

## System-Wide Impact
- **Interaction graph**: new tool is a leaf read (one SELECT, guarded). Registered in `_TOOL_HANDLERS`
  -> auto-exposed on `/chat`, the Agent-SDK loop, and the MCP server (auto-enumerated from
  `RESEARCH_TOOLS`). No callbacks/migrations/writes.
- **Error propagation**: tool swallows all exceptions -> generic JSON error (mirrors siblings); the
  agent treats a not-found error as the refusal signal. No new error classes.
- **State lifecycle**: none (read-only).
- **API surface parity**: `/chat`, Agent-SDK, and MCP all reach the tool via the single
  `_TOOL_HANDLERS` registration -- one registration covers all three (no parallel edits).
- **Frozen-core integrity**: `grading_contract_hash` MUST stay unmoved (no grader/vocab change);
  only `content_hash` moves (templates.py). `solvers.py` is in neither hash.

## Dependencies & Risks
- **Primary risk (the whole premise)**: sonnet may ace the long loop like covoting -> negative
  result. **Mitigated by the gate** -- Phases 1-2 are cheap (one tool + minimal generator + seam);
  we spend the frozen-suite effort ONLY after sonnet is shown to struggle. A negative result is a
  legitimate, valuable outcome (closes the "is the long loop frontier-hard?" question).
- **∅-vs-refuse mislabeling** (covoting's bug): mitigated by the clean tool-signal partition above
  and a per-emit assert; the drift guard + twin tests (Phase 3) lock it.
- **Answer-unit drift**: gold and submission are both internal `bill_id` strings (the unit the tools
  hand the agent); the drift guard asserts gold == the two-tool loop yield.
- **agent-sdk is slower** (spawns the engine per rollout) but not rate-walled; budget time for the
  screen.
- **ruff E501 on comments/docstrings** (recurring): reflow manually, ASCII-only.

## Sources & References
- **Origin scope**: docs/scopes/2026-06-28-member-sponsorship-outcomes-multihop-scope.md (Congress
  110; band 15-50; screen-gate; loop-is-the-difficulty / anti-pre-join).
- **Tool mirror**: `src/api/chat.py:310-345` (`_tool_get_bill_cosponsors`), `:264-307`
  (`_tool_get_bill_votes`), `:713-730` (`_TOOL_HANDLERS`); `src/llm/tools.py:98-114`
  (`get_bill_cosponsors` schema).
- **Template/solver mirror**: `lab/templates.py` (`generate_covoting_disagreement` ~1135-1278,
  registry ~1490, `_covoting_prompt` ~1125, `_covoting_refusal` ~1281); `lab/solvers.py`
  (SUBMIT_SCHEMAS ~212, SET_MATCH_FIELD ~225, TEMPLATE_TOOLS ~258, the 3 solvers ~36-80);
  `lab/graders.py` (`set_match` ~70/107, `REFUSAL` ~21); `lab/trace.py:34-61` (hash split);
  `lab/harness.py:44-54` (`Instance`).
- **Gate manifests**: `tests/test_lab/conftest.py:25` (sponsorships already present);
  `tests/test_mcp/test_server.py:31,35,61-78` (the only edit: +1 tool).
- **Strategy/precedent memory**: [[feedback_lab_find_hard_families]],
  [[project_condorcet_covoting_discrimination_pending]], [[project_condorcet_build_backlog]],
  [[project_condorcet_eval_philosophy]].

---

## Panel resolutions (rev 2 -- folded, authoritative)
The 5-lens panel SUPERSEDES the body where they conflict. Headline: the original screen had
**four independent ways to draw a false "hard" verdict** (turn-cap truncation, system-prompt
refuse-on-empty, an unwired screen-band, and off-by-one precision read as incapacity). All are
fixed below. Panel's honest prior: **~75-80% sonnet aces this** (a probable, still-valuable
negative) -- so the cheap, HARDENED screen must be trustworthy before we read its verdict.

**PR-1 (P1, blocker) -- Turn budget truncates the long loop -> false "hard".** `_asolve_sdk`
defaults `max_turns=14` (solvers.py:803); a sequential 30-50-bill loop needs ~32-52 turns -> a
careful model hits the wall -> `result_subtype != "success"` -> NO_ANSWER -> scored as
loop-dropping. **Fix (Phase 2 prereq, run.py is in NEITHER hash):** add `--max-turns` (and
`--max-budget-usd`) passthrough in `lab/run.py` -> `AgentSolver(..., max_turns=args.max_turns)`;
run the screen with `--max-turns 60`. At the gate, **EXCLUDE any rollout with
`result_subtype != "success"` from the pass-rate denominator** (run.py already surfaces the
non-success/truncation warning ~221-233). "Read 2-3 traces" is not enough -- make the exclusion
explicit so a turn cap is never scored as a drop.

**PR-2 (P1, blocker) -- The 30-50 screen band is unreachable dead code.** Every call site invokes
`template.generate(conn, n, seed, pre)` positionally (run.py:136/139, harness.py:123, batch.py:287);
a keyword-only `band=` default always wins, so the screen would run the diluted 15-50 band. **Fix:**
DROP the `band` kwarg + the dual constant entirely. Phase 2 generator hardcodes the SCREEN config
(band `(30,50)` AND filter to `|gold|>=1`, emit n answerable-only). Phase 3 EDITS the generator to
the FROZEN config (band `(15,50)`, natural empties + twins). The generator evolves across phases
(content_hash moves both times; grading_contract_hash unmoved). Do NOT plumb `--band` through run.py
(the over-investment the gate avoids).

**PR-3 (P1, blocker) -- Answer-unit trap: the tool ships two id-shaped fields.** Returning both
`bill_id` and `identifier` (e.g. `hr1234`) lets a correct-loop model submit `identifier` and fail
8/8 (gold = `Bill.id`; covoting was safe because its readability field was `name`). **Fix:** return
ONLY `{"bill_id": ...}` from `get_member_sponsorships` (the loop needs nothing else -- `get_bill_votes`
keys on `bill_id`). Drop `identifier` from the payload and the schema.

**PR-4 (P2, blocker) -- Refuse-on-empty (the covoting class, agent-side).** The shared
`_AGENT_SYSTEM_PROMPT` (solvers.py:324-334) says "empty tool result -> `refused=true`". Here an empty
`get_bill_votes.roll_calls` is the NORMAL "no roll-call vote" signal, and the answerable-EMPTY case
has EVERY per-bill call empty -> a literal agent refuses -> over-refusal FAIL though `[]` is correct;
this also corrupts normal instances (~20/24 calls are empty). **Fix (template-local, does NOT touch
the shared prompt):** state in the TASK PROMPT that an empty roll-call result for a bill means it
received no roll-call vote -- exclude it and continue, do NOT refuse; refuse ONLY when the member
cannot be found (`get_member_sponsorships` errors). Uniform across all twins (no leak). The gate
trace-read must classify any refuse-on-empty as a prompt artifact, not loop-dropping.

**PR-5 (P2) -- Gate checklist understated: `tests/test_lab/test_agent_seam.py` (2 asserts).**
`test_template_tools_covers_every_registered_template` (every registered template_id in
TEMPLATE_TOOLS) -> the templates.py registry entry and the solvers.py TEMPLATE_TOOLS entry MUST land
in the same Phase-2 commit. `test_research_tool_for_resolves_every_provisioned_tool` (every
TEMPLATE_TOOLS tool in RESEARCH_TOOLS) -> `get_member_sponsorships` must be in RESEARCH_TOOLS
(Phase 1) before/with the seam. Phase 1's STOP point stays green (no registry/TEMPLATE_TOOLS entry
yet). Add both to the Phase-2 gate checklist. (Frozen-core verdict otherwise CLEAN: grading_contract_
hash unmoved, content_hash moves via templates.py only, solvers.py in neither hash, test_hashes split
holds, set_match reusable for bill_id strings, the conftest/`_MODELS` manifests already cover
`sponsorships`/`Sponsorship` -- only the test_mcp 16->17 edit is needed there.)

**PR-6 (P1) -- Instance pseudocode omits two REQUIRED fields.** `harness.Instance` requires
`instance_id` and `tier` (no defaults). Add `instance_id=f"{TEMPLATE_LEAD_SPONSOR_OUTCOMES}:{seed}:
{person_id}"` and `tier="C"` to every emitted Instance (the body pseudocode would not construct).

**PR-7 (P2) -- Screen power + diff-distance instrumentation.** n=8 is underpowered (at true p=0.85,
`<=5/8` fires ~11% on noise; the 3-bucket bar treats a 1-instance swing as decisive). **Fix:** raise
the screen to **n=12**, select `|gold|>=1` so every screen instance forces a real loop, and compute
the denominator from the actual answerable count (NOT a hardcoded /8; ~10% of the band are empty).
**Instrument per-rollout symmetric-difference vs gold.** A "proceed (gradient)" verdict REQUIRES
large/systematic diffs or genuine truncation-free drops -- NOT off-by-one near-misses (that is the
covoting precision-at-scale axis, already covered, not new frontier signal). set_match all-or-nothing
alone cannot tell "drops one bill" from "fundamentally can't"; the diff distribution can.

**PR-8 (P2/P3) -- Concrete trace-read artifact checklist (replaces "read 2-3 traces").** Per FAILING
rollout, before crediting "loop-dropping": (a) `result_subtype == "success"` (not a turn/budget cap);
(b) actual `get_bill_votes` call count == the member's sponsorship count (a short count = early-stop/
cap, not a careful drop); (c) the submission is not a deliberate "representative sample"; (d) did the
model BATCH parallel `get_bill_votes` (collapses the "sequential loop" premise) or serialize? Also
pre-register "sonnet aces" as the expected outcome so a near-ace isn't rationalized into a gradient.

**PR-9 (P2) -- Vacuous-gate preflight (Congress-110 vote coverage).** The vote tables were historically
empty (Track-A backfill); if 110 roll-calls weren't ingested, every gold = `set()` -> a 0/0 gate.
Before spending the screen, run the gold SQL over the sampled members and assert the `|gold|>=1`
count > 0.

**PR-10 (P2) -- Tool-test mirror points at the wrong file.** The `get_bill_cosponsors` tool test lives
in `tests/test_api/test_provenance_tools.py` (NOT `test_vote_tool.py`, which is `get_vote_event`
only). The hermetic not-found guard needs TWO sequential `db.execute` returns -- `AsyncMock(side_effect=
[<empty rows>, <none>])` (empty result, then `None` from the existence check) -- more involved than
the single-mock `test_vote_tool` pattern.

**PR-11 -- PowerShell invocation (primary shell).** The body's `PYTHONPATH=. uv run ...` is bash-only.
Screen command:
`$env:PYTHONPATH='.'; uv run python -m lab.run --agent --template lead_sponsor_outcomes --model claude-sonnet-4-6 --backend agent-sdk --n 12 --seed 42 --max-turns 60`
(repeat `--model claude-haiku-4-5`). `--backend agent-sdk` is REQUIRED (default is messages-api, which
rate-walls). Backend/flag/model ids verified valid in run.py.

**PR-12 (P2) -- Refusal twin = fabricated (name, id) PAIR.** The shared prompt needs a `name`, which a
nonexistent person lacks. Fabricate BOTH a seed-derived synthetic name AND a synthetic id absent from
`people` (the id is what the tool keys on), with a per-emit `SELECT 1 FROM people WHERE id=%s` IS NULL
assert. `grader="refusal_correct"`, `gold=REFUSAL`, `is_refusal=True`,
`refusal_reason="member_not_in_data"`.

**PR-13 (P2) -- Move the emit-assert into Phase 2.** `assert inst.is_refusal == (inst.gold == REFUSAL)`
is one free line and is the exact guard against the covoting ∅-vs-refuse mislabel; Phase 2 emits
natural answerable-EMPTY instances, so it is meaningful immediately (don't defer with the twins).

**PR-14 (minor) -- Phase-3 drift guard includes `kind=="empty"`.** Unlike covoting's errored cross-body
twin, the answerable-EMPTY member here IS drift-checkable (real bills, all unvoted) -- include it for
stronger coverage. And KEEP `get_bill_votes` (do NOT swap in `list_vote_events`, which omits NULL-tally
events and would diverge from the gold's `EXISTS vote_events`).

**PR-15 (note) -- Keep `person_id`-handed for the gate.** Loop-isolation + signal cleanliness (Congress-
110 cross-congress name collisions) beat realism here. If gate-positive, Phase 3 documents the
id-in-prompt as a deliberate loop-isolation artifact (or adds a name+`find_people` realism variant) so
the eval isn't mis-sold as a realistic research flow.

**Confirmed SOUND (do not re-litigate):** gold SQL is correct, no double-count (the
`UniqueConstraint(bill_id, person_id, classification)` guarantees <=1 primary row/bill; `vote_events`
has no session column so a 110 bill's vote can't be mis-attributed); the drift equality
`gold == {b in get_member_sponsorships if get_bill_votes(b) non-empty}` holds EXACTLY (`get_bill_votes`
filters `bill_id` only, no chamber/result filter); determinism via `sample()`'s `sha256(seed:id)`
re-sort (no `ORDER BY` needed); secrets clean (`_safe_err` redacts `sk-ant-*` on both arms, agent-sdk
pops `ANTHROPIC_API_KEY`, no key path into `lab/runs/*.jsonl`); the tool's guarded body leaks no
traceback; `_TOOL_HANDLERS` (not `_HARNESS_REQUIRED_TOOLS`) is correct; `LegislativeSession`/`Person`
imports already exist in chat.py; the defensive `DISTINCT` is harmless.
