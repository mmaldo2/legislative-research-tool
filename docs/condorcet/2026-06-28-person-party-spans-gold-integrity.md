---
date: 2026-06-28
topic: person_party_spans gold-integrity — as-of party diverges from the Clerk's recorded party
type: data-integrity-finding
status: open
severity: medium
found-by: ablation pass-2 trace read (the trust bar)
affects: person_party_spans, vote-time party resolution (get_vote_event), family9.member_party_at_vote gold
---

# Finding: `person_party_spans` as-of party diverges from the official roll-call record in the switch window

## Summary
The tool-surface ablation pass 2 (point-in-time party) was read at the trace level before trusting
its numbers. The read surfaced a **data-integrity issue in `person_party_spans`**, not a model
behavior: for party-switchers, our as-of (vote-time) party can **disagree with the House Clerk's
official recorded party for that very vote**, and in at least one case it **contradicts our own
`people.party`**. The divergence concentrates in the **switch-gap window** (between a member's
*announced* switch and the *officially recorded* change) — which is exactly the window any vote-time-
party feature is most likely to be queried about.

This was the decisive reframe of pass 2: what the aggregate metric counted as web "hallucination"
(confident-wrong) was, on inspection, **web correctly reading the authoritative primary source (the
Clerk roll-call XML) while our gold was wrong/contestable**. See the pass-2 plan's Phase 4.

## Evidence (verified against the live DB, 2026-06-28)

### Case 1 — Rep. Kevin Kiley, vote `us-house-119-2026-0088` (2026-03-17)
- **Our gold (`person_party_spans` as-of)** = `I`. Spans:
  `R [2023-01-03..2025-01-03)`, `R [2025-01-03..2026-03-09)`, **`I [2026-03-09..2027-01-04)` ← covers the vote**.
  The span flips to `I` on **2026-03-09** — his *announcement* date.
- **Our own `people.party` (current)** = **`R`** (and the name tag is `[R-CA-3]`).
  → **Internal inconsistency:** the span says `I`-now while `people.party` says `R`-now.
- **House Clerk roll-call XML** (`clerk.house.gov/evs/2026/roll088.xml`, read by the web arm):
  recorded **`R`**, with `Independent = 0` in the party totals.
- Three independent signals (Clerk record, our `people.party`, the name tag) say **R**; only the
  `person_party_spans` as-of value says `I`. The `I` span is the outlier — a likely **premature flip
  at the announcement date** rather than the officially-recorded change.

### Case 2 — Del. Gregorio Sablan, vote `us-house-111-2009-0022` (2009-01-15)
- **Our gold (as-of)** = `I`. Spans: **`I [2009-01-06..2009-02-23)` ← covers the vote**, then
  `D [2009-02-23..…)`. The span flips to `D` on **2009-02-23**.
- **House Clerk roll-call XML** (`clerk.house.gov/evs/2009/roll022.xml`): recorded **`D`**.
- **Our `people.party` (current)** = `D`.
- Sablan was a *formal Independent* (Covenant Party) who caucused with Democrats; the date he
  "became D" is genuinely contestable (our spans: 2009-02-23; the Clerk's contemporaneous record: D
  from the vote). This is a **definitional/timing ambiguity**, softer than Case 1, but it still means
  the as-of gold is not the authoritative answer to "what party was recorded for this vote."

## Root-cause hypothesis
`person_party_spans` appears to be constructed by flipping a member's party at **announced /
intended** switch dates, which can lead the *officially recorded* party (what the Clerk attributes on
each roll call). For the gap between announcement and official record:
- the as-of party is wrong relative to the Clerk's contemporaneous record, and
- (Case 1) it can even contradict our own `people.party`.

The backfill source/date logic is `scripts`/`src.cli backfill_person_party_spans` (CLI:
`Backfill person_party_spans (vote-time party) from current + historical legislators`).

## Impact
- **`get_vote_event`** returns the as-of party from these spans — so any product surface that shows
  "the party they were representing when they voted" inherits the divergence for switch-window votes.
- **`family9.member_party_at_vote`** gold is built from the same as-of join → its hardest (switch-
  year) instances carry contestable gold. The template is sound *logic*; the *source data* is the
  problem. **Do not promote it to a trusted Family 9 benchmark slice until the gold is reconciled.**
- Aggregate party templates (`party_breakdown` / `party_defection` / `crossed_party`) use the same
  as-of join, but those are gated to *completed* congresses and reconciled events; the switch-gap
  divergence is most acute for very recent / edge switchers (Kiley 2026) and delegates (Sablan).

## Recommended remediation (not yet done)
1. **Reconcile the gold source.** The House Clerk roll-call XML records a `party` attribute *per
   member per vote* — the authoritative "party they were recorded under." Consider sourcing vote-time
   party from the Clerk record directly (or validating `person_party_spans` against it) rather than
   from announced-switch-date spans.
2. **Fix the Kiley internal inconsistency** (`person_party_spans` says `I`-now, `people.party` says
   `R`-now) — at minimum the two should agree on the *current* party.
3. **Decide the definition:** "party representing when they voted" = officially-recorded party (Clerk)
   vs formal/announced affiliation. The Clerk record is the defensible, citable answer and is what a
   primary-source-reading agent will return; align our gold to it.

## Provenance
Found by reading the pass-2 ablation web-arm traces (the "trust bar": read traces before trusting any
pass-rate). The 4 web "hallucinations" on the switcher subset all traced to these 2 cells, where the
web arm fetched the Clerk XML and reported a party our gold disagreed with. Cross-ref:
`docs/plans/2026-06-27-feat-ablation-pass2-pointintime-plan.md` (Phase 4),
`lab/runs/ablation_*_web_switcher_*.jsonl` (the trace records).
