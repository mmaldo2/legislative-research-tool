---
date: 2026-06-28
topic: Family 2 cosponsor×vote join (cosponsored_and_voted_against)
scope-mode: hold
status: approved
---

# Scope: Family 2 — cosponsored bill Y AND voted against it

## Problem
First Family 2 (sponsorship) slice and the lab's first **Tier-3 two-table join** — "which members
cosponsored bill Y AND voted against it." The doc's "first place frontier models start to fabricate":
high model-discrimination, data-ready. Moves the benchmark onto the fabrication frontier (see the
build backlog `docs/condorcet/2026-06-28-task-suite-build-backlog.md`).

## In Scope
- ONE template `family2.cosponsored_and_voted_against`. gold = the **SET of person_ids** who
  cosponsored bill Y AND voted **nay** on its single roll call (**∅ valid** when all cosponsors
  supported it); grader = **set_match** (the `crossed_party` `member_ids` shape — no new grader).
- Eligibility: **single-roll-call bills** (exactly 1 vote_event) **with cosponsors** (≈2,904 universe;
  federal-only — all voted bills are `us`). "cosponsored" = classification ∈ {cosponsor,
  original-cosponsor} (excludes `primary`).
- **Stratified sampling across ∅-gold (94%) and non-∅-gold (6%)** so both "don't fabricate a defector"
  and "find the defectors" are exercised.
- **Refusal twins** (cite_record_id pattern): nonexistent bill; a real member who did not cosponsor /
  a bill with no roll call → REFUSAL.
- **One new minimal tool** `get_bill_cosponsors` (bill → cosponsor person_ids + names) for the OURS
  arm + wiring (TEMPLATE_TOOLS=[get_bill_cosponsors, get_bill_votes, get_vote_event], SUBMIT_SCHEMAS,
  SET_MATCH_FIELD). Deterministic invariants + requires_pg gold-validity tests.

## Out of Scope
- Other Family 2 templates (never-cross-aisle, blocs, lead-sponsor passage rate) — fast-follows that
  reuse the new tool.
- Multi-roll-call bills / a "passage vote" C-def — deferred; the single-roll-call gate keeps this pure
  tier-C with no registry definition.
- Any tool-surface ablation on this template — the moat work stream is paused.

## Key Constraints
- Frozen core untouched (graders/scoring/validate_gold/vocab/existing gold) → `grading_contract_hash`
  UNMOVED; `content_hash` moves (new template — expected). set_match reused, NO new grader.
- The new tool is **product code** (src/llm/tools.py RESEARCH_TOOLS + a handler in src/api/chat.py,
  mirroring get_bill_votes), NOT frozen-core. Cosponsorship has no party/point-in-time dimension.

## Codebase Context
- Siblings to mirror: `crossed_party` (set_match `member_ids`, ∅-valid) + `cite_record_id`
  (single-roll-call gate, refusal twins, bill-keyed) in `lab/templates.py`.
- `src/models/sponsorship.py` (bill_id, person_id, classification; UniqueConstraint). `get_bill_detail`
  exposes sponsors but is heavy/leaky (text + AI summary) → a clean minimal `get_bill_cosponsors`.
- Verified 2026-06-28: 5,707 bills w/ both; 2,904 single-roll-call w/ cosponsors; 6% have a defecting
  cosponsor.

## Open Questions (for /ce:plan)
- The ∅ vs non-∅ stratification ratio (the 94/6 skew) — a floor of non-∅ instances?
- `get_bill_cosponsors`: cosponsors only vs all sponsors + a role flag (lean: cosponsors only).
- Refusal twins: reuse cite_record_id's structural-disjoint no-link member, or a simpler
  "member didn't cosponsor this bill"?
