---
title: "feat(lab): gold-vs-Clerk reconciliation for the harness-lift study"
type: feat
status: active
date: 2026-06-29
origin: docs/scopes/2026-06-29-gold-vs-clerk-reconciliation-scope.md
---

# feat(lab): gold-vs-Clerk reconciliation

## Overview
Before any lift cell runs (pre-reg `3fa0784`), verify the member_summary / pairwise gold for the
**118th House** equals the authoritative public record (`clerk.house.gov`) — else a web arm reading
the Clerk correctly is graded FAIL against a divergent gold (spurious "lift"). **Read-only**: emits a
keep/drop instance list + a divergence report; never mutates gold or the frozen core.

**Grounded mechanism (from `src/ingestion/votes.py`):** the ingester fetches every House roll
`1..max_roll` per year via `house_years_for_congress(118)` → `[2023, 2024]` + `_house_max_roll(year)`,
but `vote_events.bill_id` is `NOT NULL`, so rolls that don't resolve to a bill are **dropped**. So
`COUNT(vote_events)` for (118, house) = the **bill-linked subset**, and the gap vs the Clerk total =
**procedural / non-bill rolls** (motions, quorum, Speaker, journal). That gap is the divergence the
study must resolve, and it's reusable code, not a mystery.

## Phase 1: Quantify the gap (READ-ONLY probe; STOP for the Q2 decision)
- [ ] Reconciliation probe (non-frozen, `lab/experiments/clerk_reconcile.py`): reuse
      `vote_parsers.house_years_for_congress` + `_house_max_roll` to get the **Clerk total** for (118,
      house) = Σ max_roll(2023, 2024); compare to `COUNT(vote_events)` for session `us-118`, chamber
      house. Report ours / Clerk / gap.
- [ ] Confirm the gap's COMPOSITION: sample ~10 missing roll numbers (`house_vote_event_id` not in our
      DB), fetch+`parse_house_roll_xml`, confirm they are non-bill/procedural (not bill-linked rolls
      we failed to parse — a parse-failure gap would be a real completeness bug, a different problem).
- [ ] Per-member magnitude: for ~5 of the n=40 (seed 42) sampled member windows, compute our
      bill-linked tally (yea/nay/other) vs the member's FULL Clerk tally (parse their votes across all
      rolls for the year). Report the per-member delta distribution.
- [ ] Politeness: reuse the ingester's throttled `httpx` client (the Clerk WAF blocks bursts).
- [ ] **STOP — present ours/Clerk/gap + composition + per-member deltas, and the Q2 decision.**

## Phase 1 RESULT (2026-06-29) — gap is SMALL + CLEAN; decision = re-scope prompt (path a)
`lab/experiments/clerk_reconcile.py` (read-only) on 118 House:
- Clerk roll-call total **1241** (2023: 724, 2024: 517); our bill-linked `vote_events` **1210**.
- **GAP = 31 (2.5%)**, and the 15 sampled missing rolls are **100% procedural** (QUORUM / ADJOURN /
  no legis_num) — ZERO parse-fails, ZERO wrong-congress, ZERO bill-not-ingested. Completeness is
  GOOD; the only divergence is the intentional bill-linked filter excluding non-legislative votes.
- Top members have exactly 1210 records (voted every bill-linked roll); their true Clerk roll-call
  count is up to 31 higher.

**Decision = Q2 path (a).** Even 2.5% is fatal for an EXACT-count comparison (a web arm counting ALL
roll calls is off by the ~31 procedural votes -> systematic FAIL vs our gold). Re-scope the
member_summary / pairwise prompt to **"roll-call votes on legislation (bills)"** so BOTH arms count
the bill-linked set. The restriction is NATURAL (votes on legislation, not quorum/adjourn) and small
(1210/1241 retained) -- not a contortion. It is a FROZEN-template prompt change (content_hash moves)
-> **run the 5-lens panel + the green gate before Phase 2.**

## ALL-31 categorization + 5-lens panel + DECISION (A) decouple (2026-06-29)
**All 31** missing 118-House rolls categorized (not just 15): **`non_bill: 31`** (QUORUM / ADJOURN /
no legis_num), **zero `bill_not_ingested`** -> `skipped_unresolved_bill == 0`. So the divergence is
PURELY the public bill-vs-procedural cut (a deterministic function of the public `legis_num` field),
not idiosyncratic ingestion -> path-(a) re-scope is DEFENSIBLE (lens 4's condition met).

**5-lens panel verdict (folded):**
- Wording (lens 1/2/5): NOT "(bills)" -- our gold = bills AND resolutions (`is_bill_ref`:
  HR/S/HRES/SRES/HJRES/SJRES/HCONRES/SCONRES) and MECHANICAL (includes motions/amendments ON a
  bill). Prompt must say "roll-call votes on bills and resolutions ... any question type." Prompt
  ONLY (NOT SUBMIT_SCHEMAS -- it's in neither hash).
- Per-member option-level spot-check REQUIRED (lens 3): the count-level reconciliation misses an
  option-swap (two members' options exchanged within an event -> bucket totals unchanged, both
  tallies corrupted). Spot-check rosters vs the Clerk, not just counts.
- STRUCTURAL (lens 3, the decision driver): member_summary/pairwise gate to `_fully_complete_windows`
  = (congress, chamber) across ALL completed congresses + BOTH chambers (run logs: us-house-110..118
  AND us-senate-*). "118 House only" -> n~=1; House-only reconciliation can't cover the Senate /
  110-117 windows. The pinned design and the frozen templates' sampling don't fit.

**DECISION (A) -- DECOUPLE (user, 2026-06-29).** The lift study (an EXPERIMENT, non-frozen) generates
its OWN single-window instances: **40 named 118-House members, bill-linked yea/nay/other gold, the
"bills and resolutions / any question type" prompt** -- NOT the frozen multi-window templates. This
makes the 118-House reconciliation (already done, gap=31 all procedural) SUFFICIENT, gives a real
n=40, and **touches NO frozen template** (no content_hash move; sidesteps the frozen-edit-bias
concern). Phase 2 below (frozen-template re-word + keep/drop artifact) is SUPERSEDED -- retained for
the record. The keep/drop artifact is dropped (lens 5: a no-op once gold==public by construction).

## Phase 2 [SUPERSEDED by decision A]: The fix (frozen-template re-word + reconciliation artifact)
Decide from Phase 1:
- **(a) Cheap re-definition (if the gap is clean = purely non-bill rolls):** re-scope the task to
  **"roll-call votes on legislation (bills)"** — reword the member_summary / pairwise PROMPTS so BOTH
  arms compute the bill-linked quantity (the web arm filters to bill votes too). Gold VALUE is already
  bill-linked, so no gold recompute — but the prompt edit touches `lab/templates.py` (**content_hash
  MOVES**; `grading_contract_hash` UNMOVED; re-run the answer-spec/agent-seam green gate). This makes
  the task fair AND honestly scoped.
- **(b) Expand ingestion (if the gap is messy / parse-failures / the bill-linked framing distorts the
  task):** OUT OF SCOPE here — it needs a nullable-`bill_id` / synthetic-event design; reassess
  whether member_summary/pairwise are the right first tasks at all.
- [ ] Build the reconciliation deliverable: for all n=40 windows/task, verify gold == public
      (bill-linked), emit a **keep/drop JSON** (`lab/runs/reconcile_118house_<ts>.json`) the
      pre-registered run filters on + the divergence report. Drop windows where ours != Clerk.
- [ ] Tests: hermetic unit tests on the pure comparison logic (synthetic ours/Clerk inputs ->
      keep/drop); a `requires_pg` smoke that the probe runs against the real DB.

## Out of Scope
Mutating gold / frozen graders; ingesting non-bill rolls (Phase-2b is a separate decision); the
Senate; the lift run itself; other templates.

## Acceptance Criteria
- [ ] Phase 1: ours/Clerk/gap reported for (118, house) + gap composition confirmed (non-bill vs
      parse-failure) + per-member delta distribution. The Q2 path chosen with the numbers.
- [ ] Phase 2: the keep/drop artifact exists and the run consumes it; if (a), the prompt re-scoping
      lands with the green gate + `grading_contract_hash` UNMOVED; divergence report written.
- [ ] Read-only re: gold values; reconciliation code is non-frozen (`lab/experiments/`).

## Risks
- **Parse-failure gap (not just non-bill):** if missing rolls include bill-linked ones we failed to
  parse, that's a real ingest bug surfacing — Phase 1's composition check catches it; handle as a
  completeness fix, not a re-definition.
- **The cheap fix contorts the task:** if "bill-linked roll calls" is an unnatural question a third
  party wouldn't ask, that's a signal (per the lift-plan panel) these aren't the right first tasks —
  a legitimate Phase-1 STOP outcome to surface, not paper over.
- **Clerk WAF / live fetch:** throttle (reuse the ingester's client); the probe is the only network
  user. Per-member full-Clerk tally is the expensive part — sample, don't exhaustively fetch.
- **Prompt re-word = frozen content change:** `content_hash` moves; keep `grading_contract_hash`
  unmoved; re-run the lab green gate (answer-spec no-leak, agent-seam).

## Sources & References
- Scope: `docs/scopes/2026-06-29-gold-vs-clerk-reconciliation-scope.md`; lift plan rev 4 (`3fa0784`).
- Code to REUSE: `src/ingestion/vote_parsers.py` (`house_years_for_congress`, `_house_max_roll` /
  `_highest_roll_number` ~L93, `parse_house_roll_xml` ~L117, `house_vote_event_id`);
  `src/ingestion/votes.py` (`_ingest_house`, the throttled client); `src/models/vote.py`
  (`VoteEvent.bill_id NOT NULL` = the divergence); `lab/templates.py` `generate_member_summary` /
  `generate_pairwise_agreement` (the gold). Design: [[project_condorcet_experimental_design]].
