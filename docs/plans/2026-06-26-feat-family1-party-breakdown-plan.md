---
title: "Family 1 Phase 3b — party_breakdown (vote-time party)"
type: feat
status: active
date: 2026-06-26
parent_plan: docs/plans/2026-06-25-feat-family1-vote-time-party-plan.md
scope: docs/scopes/2026-06-24-family1-harness-scope.md
registry: docs/condorcet/registry-open-questions.md
branch: feat/lab-party-breakdown (off main — #31/#32/#33 merged)
revision: 2 (post 5-lens adversarial panel)
---

# Family 1 Phase 3b — `party_breakdown` (vote-time party) ✨

> **First party-keyed lab template.** Reads each voter's **vote-time** party from `person_party_spans`
> (Phase 3a, PR #33 merged) via the half-open as-of-date join, and reports a single party's yea/nay
> split. `party_majority` is **not** needed (counts only) — defection/crossed are 3c. Design blessed
> in a design chat; this revision folds a 5-lens panel.

> **Revision 2 — folds the panel.** Material changes: **(1) the gate checks EXACTLY ONE span**
> (`HAVING COUNT(span) <> 1`), not "has a span" — an overlapping span would otherwise double-count a
> party (overlap-freeness is a 3a *data fact*, not a DB invariant, and `person_party_spans` is now a
> maintained gold table). **(2) explicit completed-congress gate** — point-in-time was only
> *incidental* (the ongoing 119th is excluded today merely by being mid-ingestion); now enforced.
> **(3) one `_party_eligible_events` helper** bundling all three gates (complete ∩ exactly-one-span ∩
> completed-congress) so 3c can't forget one. **(4) sample a party with ≥2 yea/nay voters** (a
> "breakdown" needs ≥2; excludes trivial single-member items that duplicate vote_lookup; party-
> agnostic, no D/R allowlist). **(5) one per-event `GROUP BY party, option` query** (derives parties
> + counts together; 0-fills `{yea,nay}`). **(6) drop "shared infra for 3c" framing** + supersede the
> Phase 2 "3c widens precompute" note (any party GROUP BY needs the spans join, so it can't be
> join-free — party stays in templates). **(7) honest trust-boundary note** (completeness is
> per-bucket count, not per-voter identity). One PR; one merged DuckDB fixture.

## Overview

Phase 2 shipped 5 party-blind templates; 3b is the first to read party — correctly, as of the vote.
`party_breakdown` answers "on roll call X, of party P, how many voted yea and how many nay?" → gold
`{yea, nay}` (counts-only, single party) via `pps.person_id = vr.person_id AND ve.vote_date >=
pps.start_date AND ve.vote_date < pps.end_date` (3a-validated: 0 overlaps, Specter golden).

The correctness core is the **eligibility gate**: a breakdown event must be **complete** (records
reconcile — Phase 2's `complete_events`), **fully resolvable** (every voter maps to *exactly one*
span), **and in a completed congress** (point-in-time). Their intersection is the only thing that
keeps a party member from being silently dropped (omission) or double-counted (overlap).

## Problem Statement / Motivation
- **Vote-time party, never `people.party`** (current-only → mis-attributes switchers).
- **Three gates, all required.** complete (every official voter recorded) ∩ exactly-one-span (every
  record maps to one party, no omission/overlap) ∩ completed-congress (no ongoing-congress leak).
- **Honest boundary:** completeness is per-bucket *count* equality, not per-voter *identity* — so
  wholeness holds **modulo the inherited assumption that `vote_records` is an identity-faithful subset
  of official voters** (the same assumption Phase 2's `member_summary`/`pairwise` rely on; stated, not
  silently claimed).

## Proposed Solution

### Locked decisions (encoded here)
1. **Gold = `{yea, nay}` counts-only, single party**, via the half-open as-of join + `vr."option" IN
   ('yea','nay')`, **0-init-accumulate** so both keys always present (an all-yea party has no `nay`
   row otherwise → `grade_fields` key-mismatch). `grader="fields"` (exists since 2a — **no
   grading-contract change**; only `content_hash` grows).
2. **`_party_eligible_events(conn, pre) -> frozenset[str]`** — ONE helper, the reusable unit, once/run,
   in `lab/templates.py`. Returns `(completed-congress dated events ∩ pre.complete_events) − {events
   with any voter mapping to ≠1 span}`. The exactly-one check is `GROUP BY vote_event_id, person_id
   HAVING COUNT(pps.id) <> 1` (catches 0 **and** >1 — does not rely on 3a's overlap-freeness). 3c
   reuses this helper.
3. **Completed-congress gate is EXPLICIT** (`sessions.end_date IS NOT NULL` via event→bill→session) —
   point-in-time is enforced, not incidental. Zero cost today (119th already excluded); future-proof.
4. **Sample a party present with ≥2 yea/nay voters** on the event (a breakdown needs ≥2 to be a real
   split; excludes trivial single-member items that duplicate `vote_lookup`). Party-agnostic — no D/R
   allowlist. Deterministic `pick_one` over the qualifying parties.
5. **One per-event query**: `SELECT pps.party, vr."option", COUNT(*) … WHERE vr.vote_event_id=%s AND
   vr."option" IN ('yea','nay') GROUP BY pps.party, vr."option"` → build `{party: {yea, nay}}`, pick a
   ≥2-voter party, gold = its `{yea, nay}`. (Derives parties-present + counts together; no second
   query, no consistency risk.)
6. **Refusal twin = synthetic nonexistent `vote_event` id** (proven absent before emit; mirror tally),
   `gold=REFUSAL`, `grader="refusal_correct"`, `refusal_reason="event_not_in_data"`; params carry a
   placeholder `party` for shape parity. *(Party-absence refusals deferred — a "valid party" registry
   def isn't blessed, and sampling only picks present parties so it can't arise here.)*
7. **`person_party_spans` = 6th lab gold table** in `REQUIRED_COLUMNS` (+ L1 ORM / L2 live drift).
8. **All new SQL = plain string literals** (not f-strings) with `%s` params, so the portability AST
   scan covers them; the as-of join stays inline per query (no interpolated join-builder).

### Tasks (one PR — no contract/precompute change, so no sub-phase split)
- **T1 — eligibility + gold in `lab/templates.py`:** `_party_eligible_events` helper (Locked #2/#3);
  `generate_party_breakdown(conn, n, seed, pre)` (Locked #1/#4/#5/#6); `TEMPLATE_PARTY_BREAKDOWN` +
  registry entry. `run.py` auto-includes it; three invariants green on live PG.
- **T2 — drift + fixtures:** add `person_party_spans` to `REQUIRED_COLUMNS` (L1+L2 auto-cover); ONE
  DuckDB fixture (`vote_events`/`vote_records`/`people`/`person_party_spans`) containing a **switcher**
  (proves vote-time ≠ current), a fully-resolvable event, and an event with an unresolvable voter —
  asserting (a) gold `{yea,nay}` vs hand literals on the resolvable event, (b) the unresolvable event
  is excluded by `_party_eligible_events`. Portability scan auto-covers the new literals.

### Architecture (current → target)
| File | Now | Target |
|------|-----|--------|
| `lab/templates.py` | 5 generators + `_fully_complete_windows` | **+** `_party_eligible_events(conn, pre)` (3-gate intersection, once/run); **+** `generate_party_breakdown`; **+** `TEMPLATE_PARTY_BREAKDOWN` + registry entry |
| `lab/run.py` | `--template` over 5 | auto-includes `party_breakdown` (choices from registry) |
| `lab/precompute.py` | `complete_events` etc. | **unchanged** (party stays in templates; precompute join-free) |
| `tests/test_lab/conftest.py` | 5 gold tables | **+** `person_party_spans`: `{id, person_id, party, start_date, end_date}` |
| `tests/test_lab/test_party_breakdown.py` | — | **new**: one DuckDB fixture (switcher + resolvable + unresolvable-voter) → gold-vs-literals + gate-exclusion |

## System-Wide Impact
- **Interaction graph.** `run()` → `precompute` (unchanged) → `generate_party_breakdown` (calls
  `_party_eligible_events` once, samples) → per (solver, instance): solve → `grade("fields")` →
  `write_trace`. Lab stays standalone psycopg2, read-only on the federal DB; **no new `src` import**
  (the ORM model is referenced only in the hermetic L1 drift test; `precompute` already imports
  `OPTION_BUCKETS`, so "no *new* src import" is the precise claim).
- **Error propagation.** Empty eligible set → existing `RuntimeError`. Malformed gold →
  `validate_gold` raises. Refusal twin proven absent before emit.
- **State lifecycle.** Append-only JSONL; read-only DB.
- **Integration scenarios.** (1) breakdown invariants on live PG; (2) DuckDB gold == hand literals on
  a **switcher** (vote-time party); (3) an unresolvable-voter event excluded by the gate; (4) the
  exactly-one-span gate excludes a synthetic overlap fixture; (5) `person_party_spans` drift L1/L2.

## Acceptance Criteria
- [x] `_party_eligible_events` = (completed-congress dated ∩ `complete_events`) − {≠1-span events},
  once/run; the exactly-one (`HAVING COUNT <> 1`) + completed-congress gates enforced (not inherited).
- [x] `generate_party_breakdown`: single-party `{yea, nay}` (0-filled) via the one per-event
  `GROUP BY party, option` query; party sampled among those with **≥2** yea/nay voters; refusal twin =
  nonexistent event.
- [x] One DuckDB fixture proves: gold vs hand literals on a **switcher** (vote-time, not current); an
  unresolvable-voter event excluded; (synthetic) overlapping-span event excluded.
- [x] `person_party_spans` in `REQUIRED_COLUMNS`; L1 + L2 drift green.
- [x] Three deterministic-solver invariants green on live PG; gold magnitudes sane (party counts ≤ the
  event's stored yea/nay totals); `grader="fields"` (no grading-contract-hash move; `content_hash`
  grows). All new SQL passes the portability scan. `ruff` + lab + project suites green.

## Alternative Approaches Considered
- **Gate = "has a span"** — rejected (panel): an overlap double-counts; gate must be exactly-one.
- **Point-in-time via complete_events alone** — rejected (panel): incidental (rides on 119th being
  mid-ingestion); explicit completed-congress gate added.
- **Any-present-party / D-R-only sampling** — rejected: ≥2-voter threshold is party-agnostic and
  excludes trivial single-member breakdowns without an allowlist.
- **Two per-event queries (parties-present + gold)** — rejected: one `GROUP BY party, option`
  suffices, no consistency risk.
- **`{yea, nay, other}`** — rejected: a yea/nay split; `other` uninteresting here.
- **"3c widens precompute scan to party" (Phase 2 note)** — **superseded**: `vote_records` has no
  party, so any party GROUP BY needs the spans join → not join-free. Party resolution stays in
  templates; 3c reuses `_party_eligible_events`.
- **Read `people.party`** — rejected (hard rule): current-only, post-dates switchers.

## Dependencies & Risks
- **Identity-faithfulness assumption (stated, not gated):** completeness is per-bucket count equality;
  a phantom/wrong-person record (same bucket, count preserved) would shift a derived-party count
  undetected. Inherited from Phase 2; documented as the trust boundary, not silently claimed.
- **Gate-join performance:** `_party_eligible_events` is a once/run `vote_records (5.4M) ×
  person_party_spans` date-range anti-join — perf review confirmed it hash-joins on `person_id` and is
  single-digit seconds (the 3a probe ran this shape). Acceptable for offline batch; not per-instance.
- **Switcher fixture is load-bearing:** without a switcher, a current-party join would pass the
  fixture — the DuckDB fixture MUST include one.
- **Pre-build verification:** confirm `_party_eligible_events` is large (~13,092 expected) before use.

## Out of Scope (do NOT build)
`party_majority` impl + `party_defection` + `crossed_party` (3c); `caucus`/`congress`/`chamber`
columns; any new grader mode; windowed party breakdowns; party-absence refusals; API/MCP surface; the
live-agent slice.

## Open Decisions (resolved)
1. **Point-in-time** — explicit completed-congress gate. *(User.)*
2. **Sampling** — party with ≥2 yea/nay voters. *(User.)*
3. **Gate location** — templates helper (`_party_eligible_events`); precompute stays join-free. *(Locked.)*
4. **No caching** — recompute the eligible set each run (simple; the join is once/run). *(Locked.)*

## Sources & References
- **Prior plans:** Phase 1/2 (`docs/plans/2026-06-25-*`), Phase 3a (`...-vote-time-party-plan.md`).
  **Scope:** `docs/scopes/2026-06-24-*`. **Registry:** `docs/condorcet/registry-open-questions.md`.
- **Code (verified):** `lab/templates.py` (`_fully_complete_windows` once/run pattern at L264;
  `generate_member_summary` 0-init-accumulate at L333; `generate_tally` refusal twin; `_in_clause`,
  `sample`/`pick_one`, `TEMPLATE_REGISTRY`); `lab/precompute.py` (`complete_events`; the `src`
  `OPTION_BUCKETS` import); `lab/harness.py` (`validate_gold` "fields" arm, `run()` single `generate`
  call); `lab/graders.py` (`fields`); `lab/solvers.py` (`WrongBaselineSolver` perturbs first int
  field); `src/models/person_party_span.py` (4 cols, half-open `end_date`); `src/models/vote.py:16`
  (`vote_date` is `Date`); `tests/test_lab/{conftest,test_gold_fixtures,test_sql_portability,test_schema_columns,test_schema_live}.py`.
- **3a validation:** as-of join → 99.60% exactly-one, 0 overlaps, Specter golden; ~13,092 eligible.

---

[![Compound Engineered](https://img.shields.io/badge/Compound-Engineered-6366f1)](https://github.com/EveryInc/compound-engineering-plugin) 🤖 Generated with [Claude Code](https://claude.com/claude-code)
