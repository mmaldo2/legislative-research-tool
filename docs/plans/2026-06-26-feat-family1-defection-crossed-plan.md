---
title: "Family 1 Phase 3c — party_majority + party_defection + crossed_party"
type: feat
status: active
date: 2026-06-26
parent_plan: docs/plans/2026-06-26-feat-family1-party-breakdown-plan.md
scope: docs/scopes/2026-06-24-family1-harness-scope.md
registry: docs/condorcet/registry-open-questions.md
branch: feat/lab-defection-crossed (off main — #31/#32/#33/#34 merged)
revision: 2 (post 5-lens adversarial panel)
---

# Family 1 Phase 3c — `party_majority` + `party_defection` + `crossed_party` ✨

> **The party-aware layer.** Resolves the `party_majority` registry definition and ships
> `party_defection` (how many crossed) + `crossed_party` (who crossed). Reuses 3b's vote-time
> machinery (`_party_eligible_events`, the per-event party-counts query). **No new gold table, no new
> grader mode.** Design blessed in a design chat; this revision folds a 5-lens panel.

> **Revision 2 — folds the panel** (no BLOCKERs; the core math — `defection = min(yea,nay)`,
> `|crossed| == defection` — was confirmed correct). Precision folds: **(1)** the defection/crossed
> candidate filter is **≥2 yea/nay AND `yea != nay`** (strict majority) — NOT breakdown's
> tie-permissive ≥2-only; centralized in one pure `_eligible_party_sides(splits)` so it can't
> diverge (a 2-2 party must be EXCLUDED — else a fabricated majority). **(2)** candidate discovery
> runs only over **sampled** events (n calls), never all ~13k eligible. **(3)** `crossed_party` uses
> ONE per-event `(party, option, person_id)` query (counts + ids from the same rows → `|crossed| ==
> defection` by construction + a runtime assert). **(4)** add an **`exact_int` arm to `validate_gold`**
> (defection is the first scalar-int gold). **(5)** retire **all** dangling `_party_majority` refs
> (precompute docstring + dataclass comment + registry line → repoint to `_party_majority_side`).
> **(6)** explicit half-open join in the crossers query; one DuckDB fixture + one test module.

## Overview

`party_majority` falls out of 3b's per-event `{party: {yea, nay}}` counts: majority = `yea` if
`yea > nay`, `nay` if `nay > yea`, else **null** (tie/zero → excluded). From that, over a
(event, party) with a non-null majority and ≥2 yea/nay voters:
- **`party_defection`** = `min(yea, nay)` (the minority/against-majority count; a bare int).
- **`crossed_party`** = the **set of person_ids** who voted the minority side (empty allowed).

Both reuse `_party_eligible_events` (completed-congress ∩ complete ∩ exactly-one-span) and vote-time
party (the half-open as-of join — never `people.party`).

## Problem Statement / Motivation
- **`party_majority` is a registry DEFINITION** (denominator/ties/absences). The blessed package
  resolves it; this phase records it and retires the reserved `NotImplementedError` slot.
- **Never fabricate a side.** Tie or zero voters → null majority → that (party, event) is **excluded**
  (never guessed). This is the load-bearing exclusion.
- **Same trust floor as 3b** — vote-time party, the three eligibility gates, and the honest
  per-bucket-count (not per-voter-identity) boundary. **Sharper for `crossed_party`:** it returns
  actual person_ids, so a phantom/wrong-person record yields a *wrong id in the set* (an identity
  error the `|crossed|==defection` check cannot catch) — documented, not silently claimed.

## Proposed Solution

### Locked decisions (encoded here)
1. **`party_majority` package (RESOLVES the registry):** denominator = the party's **yea+nay** voters
   (absences/present excluded); majority = the **strict** majority side; **tie or zero → null →
   excluded**. Implemented as `_party_majority_side(yea, nay) -> Literal["yea","nay"] | None` (strict
   `>`; tie/zero → None) in `lab/templates.py`.
2. **Eligibility predicate (one home):** `_eligible_party_sides(splits) -> dict[party, side]` =
   `{p: side for p, c in splits.items() if c["yea"]+c["nay"] >= 2 and (side := _party_majority_side(
   c["yea"], c["nay"])) is not None}`. This is **non-null majority AND ≥2 yea/nay voters** (a (1,0)
   party has a non-null majority but is excluded by ≥2; a (2,2) tie is excluded by null majority).
   Both generators use it; **breakdown KEEPS its tie-permissive ≥2-only filter** (a counts-only
   breakdown of a tied party is valid) — only the *SQL* is shared, not the predicate.
3. **`party_defection`** — gold = `min(yea, nay)`, a bare int; `grader="exact_int"`. No extra query
   (from `_event_party_splits` counts).
4. **`crossed_party`** — ONE per-event query returns `(party, vr."option", person_id)` rows (via the
   half-open as-of join, `option IN ('yea','nay')`); build per-party counts → `_eligible_party_sides`
   → pick party → minority option = the non-majority side → gold = the **set** of that party's
   person_ids on the minority option. `grader="set_match"`, **empty set allowed** (set → sorted list
   at the trace boundary). **`assert len(gold) == min(yea, nay)`** for the chosen party (cheap
   consistency cross-check).
5. **Sampling** = mirror 3b: `chosen = sample(sorted(_party_eligible_events(conn, pre)), n, seed)`;
   per **chosen** event compute splits → eligible party-sides → `pick_one(sorted(parties), seed)`;
   `continue` if none. One (event, party) instance per sampled event. **Never** iterate splits over
   the full ~13k eligible set.
6. **Refusal twin (both)** = synthetic nonexistent `vote_event` id (proven absent before emit; mirror
   3b), `gold=REFUSAL`, `grader="refusal_correct"`, `refusal_reason="event_not_in_data"`, placeholder
   `party` param.
7. **`WrongBaselineSolver` bare-int arm** — `if isinstance(gold, int) and not isinstance(gold, bool):
   return gold + 1` **before** the option loop (defection is the first scalar-int gold; today an int
   gold falls to the option loop → returns a str → `format_valid=0` malformed, breaking the
   wrong-baseline invariant). One `if`, nothing more.
8. **`validate_gold` `exact_int` arm** — add `grader == "exact_int"` → require `isinstance(gold, int)
   and not isinstance(gold, bool)` (additive gold-gate, mirrors the `fields`/`set_match` arms from
   2a; scalar-int becomes a first-class validated shape). `0` is a valid gold.
9. **Retire `party_majority` reservation everywhere:** delete `lab/precompute.py::_party_majority` +
   its `Precomputed` comment (`:49`) + the module-docstring reservation note (`:13-14`); remove
   `tests/test_lab/test_precompute.py::TestPartyMajorityReserved`; **repoint** the registry line
   (`registry-open-questions.md:47` "Reserved in `lab/precompute.py::_party_majority`") to
   `lab/templates._party_majority_side` under a **RESOLVED** banner.

### Architecture (current → target)
| File | Now | Target |
|------|-----|--------|
| `lab/templates.py` | 6 generators + `_party_eligible_events` | **+** `_party_majority_side`, `_event_party_splits` (breakdown refactored onto it), `_eligible_party_sides`; **+** `generate_party_defection`, `generate_crossed_party`; **+** 2 `TEMPLATE_*` + registry |
| `lab/solvers.py` | dict/set/scalar-option arms | **+** bare-int arm (`gold+1`) before the option loop |
| `lab/harness.py` | `validate_gold` fields/set_match arms | **+** `exact_int` arm (additive) |
| `lab/precompute.py` | `_party_majority` stub + reservation comments | **retire** stub + both comments |
| `lab/run.py` | registry over 6 | auto-includes the 2 new templates |
| `tests/test_lab/test_precompute.py` | `TestPartyMajorityReserved` | **remove** |
| `tests/test_lab/test_party_aware.py` | — | **new** (one module): DuckDB fixture (2-1 / 2-0 / 1-1-excluded / 2-2-breakdown-includes-defection-excludes / switcher) + WrongBaseline int arm |
| `docs/condorcet/registry-open-questions.md` | `party_majority` OPEN | mark **RESOLVED** (blessed package); repoint the code ref |

### Gold SQL (plain string literals; quoted `vr."option"`; half-open as-of join)
- **splits** (shared; the 3b query): `SELECT pps.party, vr."option", COUNT(*) … JOIN
  person_party_spans pps ON pps.person_id=vr.person_id AND ve.vote_date >= pps.start_date AND
  ve.vote_date < pps.end_date WHERE vr.vote_event_id=%s AND vr."option" IN ('yea','nay') GROUP BY
  pps.party, vr."option"`.
- **crossers** (crossed_party; ONE query, same as-of join): `SELECT pps.party, vr."option",
  vr.person_id FROM vote_records vr JOIN vote_events ve ON ve.id=vr.vote_event_id JOIN
  person_party_spans pps ON pps.person_id=vr.person_id AND ve.vote_date >= pps.start_date AND
  ve.vote_date < pps.end_date WHERE vr.vote_event_id=%s AND vr."option" IN ('yea','nay')` → group in
  Python: per-party counts (→ `_eligible_party_sides`) + person_ids per (party, option); gold = the
  chosen party's minority-option id set.

## System-Wide Impact
- **Interaction graph.** `run()` → `precompute` (unchanged) → generator (one `_party_eligible_events`
  call, then per **sampled** event: splits/crossers query + `_eligible_party_sides` + `pick_one`) →
  grade (`exact_int`/`set_match`) → `write_trace`. Lab standalone psycopg2, read-only; no new `src`
  import. `solvers.py` edit is in neither hash set (intended); `content_hash` moves (templates +
  precompute), `grading_contract_hash` unchanged (no grader edit).
- **Error propagation.** Null-majority (tie/zero) → not a candidate (never graded — no guessed side).
  Empty eligible/candidate set → existing `RuntimeError`. Malformed gold → `validate_gold` raises
  (now incl. the `exact_int` arm).
- **State lifecycle.** Append-only JSONL; read-only DB.
- **Integration scenarios.** (1) both invariants on live PG incl. the bare-int wrong-baseline; (2)
  DuckDB: 2-1 → defection 1 / crossed {x}; (3) 2-0 → defection 0 / crossed ∅; (4) 1-1 & 2-2 tied →
  excluded (no instance); (5) switcher → vote-time; (6) `assert len(crossed)==defection`.

## Acceptance Criteria
- [x] `_party_majority_side` (strict; tie/zero→None, `Literal` type); `_eligible_party_sides` (≥2 AND
  non-null majority) is the single home of the defection/crossed predicate; breakdown keeps ≥2-only.
- [x] `party_defection` gold = `min(yea,nay)` (`exact_int`); `crossed_party` gold = minority person_id
  set (`set_match`, ∅ allowed) from ONE per-event query, with `assert len(gold)==min(yea,nay)`.
- [x] Candidate discovery only over **sampled** events; refusal twin = nonexistent event.
- [x] `_event_party_splits` extracted; `generate_party_breakdown` refactored onto it; 3b tests pass
  unchanged.
- [x] `WrongBaselineSolver` bare-int arm; `validate_gold` `exact_int` arm; the wrong-baseline
  invariant holds for defection (decision==1 ∧ answer_correct==0, NOT format_valid=0); unit-tested.
- [x] `party_majority` RESOLVED in the registry; precompute stub + both comments + the registry
  code-ref repointed; `TestPartyMajorityReserved` removed; **no dangling `_party_majority` refs**
  (grep clean).
- [x] One DuckDB fixture/module proves 2-1, 2-0/∅, 1-1+2-2 exclusion, switcher (vote-time) vs hand
  literals. Three deterministic-solver invariants green on live PG for both templates; gold sane
  (defection ≤ ⌊(yea+nay)/2⌋; |crossed|==defection). `grading_contract_hash` unchanged; `content_hash`
  grows. `ruff` + lab + project suites green.

## Alternative Approaches Considered
- **Reuse breakdown's ≥2-only candidate filter** — rejected (panel): admits a 2-2 tie → fabricated
  majority. defection/crossed need `≥2 AND yea!=nay`, centralized in `_eligible_party_sides`.
- **Iterate splits over all ~13k eligible to pre-build candidates** — rejected (panel perf): ~13k
  per-event queries; compute splits only for sampled events.
- **crossed: separate splits + minority-id queries** — rejected: ONE `(party, option, person_id)`
  query gives both counts and ids (|crossed|==defection by construction).
- **party_majority in precompute / a non-strict or tie-broken majority** — rejected (hard rule /
  blessed package): templates (needs the spans join); strict; ties → null → excluded.
- **defection = {defectors, majority_side} dict / crossed requires ≥1 defector** — rejected (user):
  bare int; ∅ is a valid answerable fact.

## Dependencies & Risks
- **Candidate filter divergence** — the single biggest correctness risk; mitigated by the one
  `_eligible_party_sides` home + a fixture asserting breakdown-includes-but-defection-excludes a 2-2.
- **Bare-int `exact_int` path is new** — WrongBaselineSolver int arm + the `validate_gold` arm close
  it; unit-tested.
- **Refactoring merged 3b breakdown** onto `_event_party_splits` — low risk (same SQL); 3b tests guard.
- **crossed identity boundary** — sharper than count templates (wrong person_id under a phantom
  record); documented.
- **Switcher fixture is load-bearing** (else a current-party join would pass).
- **Pre-build:** confirm the candidate pool (≥2 yea/nay, non-null majority, over eligible events) is
  large (expected huge — most events have D and R each with many yea/nay).

## Out of Scope (do NOT build)
`caucus`/`congress`/`chamber` columns; any new grader mode; windowed party-aware templates; agent/MCP
surface; live-agent slice; party-absence refusals (deferred, as in 3b).

## Open Decisions (resolved)
1. **defection = bare int (`exact_int`)** — *(user)*. 2. **crossed allows ∅** — *(user)*.
3. **party_majority in templates; precompute reservation fully retired** — *(locked + panel)*.
4. **Extract `_event_party_splits`, refactor breakdown** — *(panel-endorsed)*.
5. **`_eligible_party_sides` is the single predicate home; breakdown keeps ≥2-only** — *(panel)*.

## Sources & References
- **Prior plans:** Phase 1/2 (`docs/plans/2026-06-25-*`), 3a, 3b (`docs/plans/2026-06-26-*`). **Scope:**
  `docs/scopes/2026-06-24-*`. **Registry:** `docs/condorcet/registry-open-questions.md` (`party_majority`).
- **Code (verified, on main post-#34):** `lab/templates.py` (`_party_eligible_events`,
  `generate_party_breakdown` per-event GROUP BY @537-546, `_in_clause`, `sample`/`pick_one`,
  registry); `lab/solvers.py:46-60` (the scalar-option branch — the int gap); `lab/graders.py:41,103`
  (`grade_exact_int`, `_format_valid` `exact_int` arm); `lab/harness.py:57-86` (`validate_gold`);
  `lab/precompute.py:13-14,49,106-117` (the reservation to retire); `lab/trace.py:130-136`
  (`_jsonable` sorts sets); `tests/test_lab/test_party_breakdown.py` (fixture style),
  `test_precompute.py:8,75-78` (`TestPartyMajorityReserved`); `src/models/vote.py:30`
  (UniqueConstraint(vote_event_id, person_id) → one party-row per voter on the gated set).
- **3a/3b validation:** as-of join 0 overlaps / Specter golden; `_party_eligible_events` once/run.

---

[![Compound Engineered](https://img.shields.io/badge/Compound-Engineered-6366f1)](https://github.com/EveryInc/compound-engineering-plugin) 🤖 Generated with [Claude Code](https://claude.com/claude-code)
