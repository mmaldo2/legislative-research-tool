---
date: 2026-06-29
topic: Gold-vs-Clerk reconciliation (the harness-lift blocker)
scope-mode: hold
status: approved
---

# Scope: Gold-vs-Clerk reconciliation

## Problem
The pre-registered lift study ([[project_condorcet_experimental_design]]; plan rev 4, commit
`3fa0784`) is invalid if our gold != the authoritative public record: a web arm reading the Clerk
correctly would be graded FAIL against a short/divergent gold -> spurious "lift." This slice
reconciles the member_summary / pairwise gold for the **118th House** against `clerk.house.gov`
BEFORE any cell runs, and emits the keep/drop instance list the run filters on. **Read-only: it
never mutates gold or the frozen core.**

Two divergence mechanisms (both must be quantified):
1. **Completeness** -- did we ingest every House roll call (count of our `vote_events` for (118,
   house) vs the Clerk's year-index totals for 2025+2026)?
2. **Definitional (the deeper one, confirmed from schema):** `vote_events.bill_id` is `NOT NULL`, so
   our store holds **only bill-linked roll calls**. The Clerk's per-member roll-call total includes
   NON-bill votes (quorum, motions, Speaker election, journal). So member_summary's "roll-call vote"
   count is really "bill-linked roll-call" count -- a web arm computing the member's FULL Clerk total
   will systematically disagree. This is the primary threat, not mere completeness.

## In Scope
- A non-frozen reconciliation script (e.g. `lab/experiments/` or `scripts/`) that, for (118, house):
  (a) fetches the Clerk year-index roll-call totals (2025+2026) -- REUSE `vote_parsers._highest_roll_
  number`; (b) compares to `COUNT(vote_events)`; (c) for the **n=40 (seed 42) sampled member windows**
  of member_summary + pairwise, spot-checks each member's gold tally (yea/nay/other) against the
  Clerk's per-member record; (d) emits a **keep/drop list** (instances where gold == public) + a
  divergence report quantifying the bill-linked gap.
- A recommendation on the task-definition fix (below), with the data to decide it.

## Out of Scope
- Mutating gold / frozen templates; ingesting non-bill roll calls (the recon INFORMS that decision,
  doesn't do it); the Senate; re-phrasing other templates; the actual lift run.

## Key Constraints
- Read-only; produces the keep/drop list the pre-registered run consumes (no gold mutation).
- Public source = `clerk.house.gov` (the SAME source we ingested from -> this is a completeness +
  definitional check, not a cross-source dispute), so it doubles as the "public gold methodology."
- Congress<->year mapping: 118th = calendar 2023 + 2024; Clerk numbers roll calls per YEAR.

## Codebase Context
- `src/ingestion/votes.py` (clerk.house.gov + senate.gov ingester) + `vote_parsers.py`
  (`_highest_roll_number` ~L93, clerk roll-call XML parser ~L117 -- REUSE both).
- `src/models/vote.py` `VoteEvent.bill_id NOT NULL` (the bill-linked-only constraint = the divergence).
- `lab/templates.py` `generate_member_summary` / `generate_pairwise_agreement` (gold over
  `vote_events`), `_fully_complete_windows` (our completeness gate, which is ingest-relative).

## Open Questions (for /ce:plan)
1. **Quantify the bill-linked gap** first: for a few 118-House members, how far is our bill-linked
   count from the Clerk's full roll-call count? (Determines whether the task is salvageable as-is.)
2. **Task-definition fix:** scope the task to "bill-linked roll calls" and say so in the prompt (so
   BOTH arms compute the same quantity, cheap) vs expand ingestion to non-bill votes (bigger, needs a
   nullable `bill_id` / synthetic-event design). Recommend after Q1's numbers.
3. Spot-check depth: count-level (member totals) vs full per-vote roster diff.
4. Where the recon code + keep/drop artifact live, and the keep/drop file format the run reads.
