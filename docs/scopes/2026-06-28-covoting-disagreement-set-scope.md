---
date: 2026-06-28
topic: Member x member co-voting disagreement-set task (Family 6 core, two-member vote join)
scope-mode: hold
status: approved
---

# Scope: Co-voting disagreement-set task

## Problem
The buildable core of Family 6 and the proven-discriminating two-member vote join: "Which 119th
roll-calls did member X and member Y vote DIFFERENTLY on?" The agent must fetch BOTH members' full
voting records and compute the symmetric difference -- a join the tool does NOT pre-join, so it
discriminates on COMPUTE-precision (not lookup). Built for **discrimination + RLVR**, not moat (moat
is LOW/public; see the backlog Meta-update -- 3 no-moat findings).

## In Scope
- New frozen template (Family 6): gold = the SET of `vote_event_id`s where X and Y BOTH cast a yea/nay
  AND their options differ; grader **`set_match`** (the `cite_record_id`/`crossed_party` shape -- NO
  new grader). Empty set is a valid answer (co-voted, never disagreed).
- **Same-party, same-chamber, same-congress (119) pairs only.** Data-validated: same-party |disagree|
  median ~15-18 House / ~14 Senate (a gradeable precision band); CROSS-party is a 200-350 lottery
  (excluded -- everyone would fail; the mirror cross-party *agreement* set is also large, so cross-party
  is out entirely). Pair selection is answer-INDEPENDENT (party+chamber+congress), so no selection bias.
- **Reuse existing tools -- NO new tool**: `find_people` (name->person_id) + `get_member_voting_record`
  (returns the full `[{vote_event_id, option}]`). `TEMPLATE_TOOLS = [find_people, get_member_voting_record]`.
- Refusal twins (`refusal_correct`): (A) a never-co-voted pair = one House + one Senate member (disjoint
  roll-calls) -> REFUSE; (B) a nonexistent member -> `get_member_voting_record` error -> REFUSE. Both
  distinct from the answerable empty set.
- Seam wiring (`SUBMIT_SCHEMAS`/`SET_MATCH_FIELD`/`TEMPLATE_TOOLS`), oracle/wrong/over-refuse invariants
  over set gold, hermetic + `requires_pg` tests (gold predicate, twins, gold-subset-of-the-two-tools),
  and a haiku/sonnet/opus discrimination run.

## Out of Scope
- **Cross-party pairs** -- both their disagreement AND agreement sets are large (200-350) -> set_match
  lottery, no discrimination. Killed by the data (the never-cross-aisle lesson).
- A pre-joined "agreement/disagreement" tool -- that would re-create the cite "answer-in-the-tool" trap.
- Ideal-point / NOMINATE computation (no clean SQL gold) + the ICPSR/GovTrack/FEC crosswalk (deferred).
- New grader modes; present/not-voting/absent as "disagreement" (only yea-vs-nay counts).

## Key Constraints
- Frozen `grading_contract_hash` UNMOVED (no `graders.py`/`scoring.py`/vote-parser change); `content_hash`
  moves (new template) -- the `cosponsored_and_voted_against` precedent.
- Disagreement universe = roll-calls where BOTH have a `yea`/`nay` record and the options differ; the
  agent must replicate this filter (get_member_voting_record returns ALL options incl. present/not_voting).
- Prompt names the two members + congress + chamber; never leaks the gold `vote_event_id`s.

## Codebase Context
- Tools (reuse): `src/api/chat.py::_tool_get_member_voting_record` (full per-roll-call records),
  `_tool_find_people`. Siblings: `lab/templates.py::generate_cosponsored_and_voted_against` (two-source
  join: stratified sampling, emit-asserts, refusal twins, gold-subset-of-tool test),
  `generate_cite_record_id` (answerable-vs-no-link-refusal structure), `generate_crossed_party`
  (member-set `set_match`). Seam: `lab/solvers.py`. Graders: `lab/graders.py` (`set_match`, frozen).

## Open Questions (for /ce:plan)
1. Pair-selection mechanics: keep |gold| in-band via same-party + an answer-independent shared-vote-count
   floor (so both members are active); accept the natural distribution (rare high-tail to ~120) or state
   a generous independent cap. Do NOT filter on |gold| itself.
2. The answerable empty-set case (same-party pair, 0 disagreements) -- include if the data has one, to
   exercise ∅-vs-refuse alongside the never-co-voted twin.
3. Determinism/leak-safety of the pair sampling + the instance id; the gold-subset check (gold ⊆ the
   symmetric difference computed from the two tools).
4. Sample size + whether to stratify House vs Senate (different vote volumes -> different bands).
