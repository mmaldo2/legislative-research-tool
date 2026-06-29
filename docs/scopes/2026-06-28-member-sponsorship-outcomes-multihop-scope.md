---
date: 2026-06-28
topic: Member lead-sponsorship outcomes -- a long-trajectory multi-hop frontier-hardness probe
scope-mode: hold
status: approved
---

# Scope: Member lead-sponsorship outcomes (long-trajectory multi-hop)

## Problem
Find a task that's hard for the FRONTIER (defeats sonnet, not just haiku), without the infra the
roadmap's hard families (8 leverage, 9 temporal) need. The covoting result showed sonnet aces a
2-call-then-compute join; the untested frontier is a LONG TOOL TRAJECTORY -- many sequential calls
where the model must orchestrate a loop and not drop items. Built for DISCRIMINATION + RLVR (moat
~dead on public data). **Frontier-hardness is UNPROVEN -- this slice is gated on a haiku+sonnet screen.**

## In Scope
- New tool **`get_member_sponsorships(person_id, congress)`** -> the member's PRIMARY-sponsored bills
  (bill_id + identifier), **NOT pre-joined to votes/status** (the per-bill loop IS the difficulty;
  pre-joining = the answer-in-tool trap). Mirror `get_bill_cosponsors` (reverse direction).
- Template (Family 2 lead-sponsor outcomes): "Which of the bills member X primary-sponsored in
  Congress C received a roll-call vote? List the bill ids." gold = the SET of X's primary-sponsored
  bills with >=1 `vote_event`; grader **`set_match`** (no new grader). The agent loops
  `get_bill_votes` over X's ~24 sponsored bills to find the ~4 that got a vote.
- **Historical congress** (e.g. 110: 17k primary sponsors, 1,961 votes). NOT 119 (0 primary sponsors).
- Member selection by primary-sponsored count **15-50** (answer-INDEPENDENT loop-length band; data:
  median 24 sponsored, |gold| median 4). Natural answerable-EMPTY members exist (35 in band: sponsored
  but none voted -> return []). Refusal twin: nonexistent member -> REFUSE.
- **SCREEN-EARLY GATE (mandatory):** after the tool + a minimal generator, run haiku+sonnet
  (`--backend agent-sdk`). If sonnet struggles on the long loop (gradient) -> finish the slice
  (refusal twin, frozen tests, requires_pg, drift guard). **If sonnet aces it -> STOP, record, reassess**
  (frontier-hardness needs infra -> Family 8) -- per [[feedback_lab_find_hard_families]].

## Out of Scope
- A pre-joined "sponsored-bills-with-vote-status" tool (collapses the loop -> sonnet aces it).
- The infra-gated hard families (8 leverage joins, 9 temporal; ideal-point/MRP/bitemporal stores).
- The `exact_int` count shape (weaker -- guessable without the set); a "passed-status" variant (later).
- New grader. The 119th (no primary-sponsor data).

## Key Constraints
- Frozen `grading_contract_hash` UNMOVED (`set_match`, no new grader); `content_hash` moves (templates.py);
  the new tool is `src/` product code (like `get_bill_cosponsors`), not frozen.
- gold = primary-sponsored bills (`classification='primary'`) with >=1 bill-linked `vote_event`; the tool
  exposes the bill list, the agent computes the vote filter -- gold == what the loop yields (drift guard).
- The screen-gate is non-negotiable: do NOT invest in the full frozen suite until sonnet is shown to
  struggle (the slice's whole premise is unproven frontier-hardness).

## Codebase Context
- New tool mirrors `src/api/chat.py::_tool_get_bill_cosponsors` (+ `RESEARCH_TOOLS`, `_TOOL_HANDLERS`, MCP
  auto-enumeration, the green-suite-gate test edits). `get_bill_votes` already exists (the per-bill check).
- Siblings: `generate_cosponsored_and_voted_against` (sponsorship x vote), `generate_covoting_disagreement`
  (set_match + twins + drift guard + the answerable-empty pattern). Graders: `lab/graders.py` (`set_match`).
- Sponsorship vocab: `classification='primary'` (lead sponsor) -- 151k rows, all in congresses 110-118.

## Open Questions (for /ce:plan)
1. Prompt: give member name + person_id (cite/covoting precedent) -> tools `[get_member_sponsorships,
   get_bill_votes]`; or include `find_people`. (Loop is the test, not name resolution.)
2. Which historical congress (110 = oldest/settled; or 117/118 = most primary sponsors). Pick one, freeze it.
3. The screen design: instance count, the explicit go/no-go bar (e.g. sonnet natural-pair pass < ~0.7 = a
   gradient worth finishing; sonnet ~aces = stop).
4. Keeping loop length in the frontier-stress band without answer-biasing (select by sponsored-count only).
