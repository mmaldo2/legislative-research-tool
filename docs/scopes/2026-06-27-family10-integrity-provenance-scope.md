---
date: 2026-06-27
topic: Condorcet Lab Family 10 — data-integrity & provenance (slice 1)
scope-mode: reduce
status: approved
---

# Scope: Family 10 (integrity / provenance) — Slice 1

## Problem
Family 10 targets the one unsurvivable failure mode — **confident hallucination**. With Family 1 done, it completes the benchmark's "trust floor": the agent never invents a record, always cites a *verifiable* source, and says "not in the data" when that's the answer. The roadmap (`docs/condorcet/lab-factual-layer-task-suite.md` → "What to build first") pairs Family 10 + Family 1 as the first thing to build.

## In Scope (slice 1 — 2 core templates, existing graders only, votes only)
- **Cite-record-id (the SPINE — the new mechanic; subsumes existence):** "Cite the roll-call vote id recording member X's position on bill Y", restricted to (member, bill) pairs with **exactly one** roll-call → gold is the **unique `vote_event_id`** → `exact` (a fabricated or wrong-but-real id fails). Adversarial twin centred on **both-real-but-no-link** (X and Y both exist, but X never voted on Y) + a fabricated-id + a nonexistent-entity variant → `refusal_correct`: refuse, don't fabricate. Needs a tiny new **`get_bill_votes(bill_id)`** tool (bill→roll-call resolution; one query on `vote_events.bill_id`).
- **Refusal-calibration family** ("correct answer is 'not in the data'") — a broad set of unanswerable tasks across record types, promoting Family 1's twin pattern to a first-class family. `refusal_correct`.
- *(Standalone boolean existence dropped — guessable 50% base-rate + overlaps Family 1; the spine already tests existence.)*

## Out of Scope (deferred, with reasons)
- **Quote-in-bill-text verification** → Family 10 **slice 2**. Federal bill text is 68/144,088 (0%). Needs a *bounded random/stratified* bill-text ingest (sample scoped + fingerprinted; the eval claim scoped to the corpus, so no selection bias) + adversarial-negative quote construction.
- **Crosswalk identity resolution** → build **with Family 6**. Federal needs the multi-id crosswalk (`congress-legislators`: ICPSR/GovTrack/FEC); we have only `bioguide_id` (OpenStates is state-only, won't help). ICPSR is also Family 6's (ideal-point) key → build once, unblock both.
- **Source-URL citation** — `bill.source_urls` is a JSONB *array* (multiple valid) → membership, not equality; `set_match` (set equality) doesn't fit. Avoid in slice 1; cite canonical unique ids instead → keeps the frozen grader contract.
- **Any new grader mode** — reuse `exact` / `refusal_correct`. The provenance value is in the TASK design, not a new grader.

## Key Constraints
- Reuses the existing `lab/` factual-layer harness (templates.py, both agent backends, graders, the frozen-spine hash discipline, the trust-bar diagnostics) — mostly NEW templates, minimal new machinery.
- Frozen core untouched: `grading_contract_hash` + `content_hash` stay unmoved (`test_hashes`).
- Same working rhythm: design-chat → /ce:plan → 5-lens panel → /ce:work, haiku checkpoint before sonnet/opus.

## Codebase Context
- Data readiness (verified 2026-06-27): votes 13,848 events / 5.4M records (existence + cite-vote-id surface = strong); `bill.source_urls` 100%, `bioguide_id` 100% (single anchor); `bill_texts` non-empty = 68 (quote-verify blocked).
- Likely NO new tool: `get_vote_event` already returns the event id + per-member records → the agent can verify existence + cite the id from it. To confirm in design-chat.

## Resolved (design-chat 2026-06-27)
1. **Citation key** → bill-keyed, restricted to **single-roll-call** (member, bill) pairs → unique `vote_event_id` → `exact`. (Multi-valid would need membership semantics / a new grader → avoided.)
2. **Tool** → add **`get_bill_votes(bill_id)`** (one query on `vote_events.bill_id`; `get_bill_detail` does not expose roll-calls). The spine is bill-keyed, so this is required.
3. **Template structure** → **2 core templates** (collapse standalone existence into the cite-or-refuse spine + a broad refusal-calibration family).
4. **Adversarial negatives** → **both-real-but-no-link** as the centerpiece (+ fabricated-id + nonexistent-entity variants).
5. **Citation scope** → **votes only** (a hallucinated vote is "brand-fatal" / highest-trust-value).

## Data note (citation uniqueness)
13,848 roll-calls, all bill-linked; 6,102 bills have roll-calls; **2,329 have multiple**, and **912,281 (member, bill) pairs map to >1 roll-call** — hence the single-roll-call restriction for a clean `exact` gold (~3,773 single-vote bills × members = ample instances).
