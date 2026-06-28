---
date: 2026-06-28
topic: Condorcet lab task-suite build backlog — value-scored priority across families
type: prioritization / process
status: living
supersedes: the implicit "go family-by-family in order" cadence
---

# Task-suite build backlog (value-scored, not family-ordered)

A living priority order for which benchmark templates to build next. **It exists so we stop picking
slices ad hoc** and instead build by value — and so the *why* behind each decision is recorded for
future context. Re-score as evidence accumulates (every live run is new discrimination data).

## Why this exists (the reframe, 2026-06-28)

We had been building **family-by-family**, which implicitly optimizes for **evaluation coverage** —
breadth across task types. But the benchmark serves **three purposes that pull in different
directions**, and coverage is the least valuable of them given what we've learned:

1. **Evaluation coverage** — measure model reliability across task types. Wants *breadth*.
2. **RLVR training signal** — reward to train a trustworthy specialist. Wants *the tiers where models
   fail fluently* + *instance abundance*.
3. **Moat / product thesis** — where our data layer beats frontier+web. Wants *tasks whose answer
   isn't on the authoritative public web*.

**The load-bearing learning (ablation pass 1 + pass 2, 2026-06):** the easy, single-hop, public-fact
tasks are exactly where frontier models are already reliable, where there is **no moat** (the ground
truth is on Congress.gov / the Clerk site — pass 2 showed web read the Clerk and *beat our gold*), and
where there is **no training signal** (everyone scores ~100%). We over-invested in Tier-1/2 public-
fact tasks. See [[project_condorcet_eval_philosophy]] and `2026-06-28-person-party-spans-gold-
integrity.md`.

## The scoring axes (and why they coincide)

Score each candidate template on three axes; **they are correlated and point the same way** — the
hard tasks discriminate models, are where the moat lives, and give the richest reward, all at once.

- **D — Discrimination.** Does it separate models / separate ours-from-web? *Evidence we have:*
  `vote_lookup` does NOT (everyone ~100%); `party_breakdown` does (haiku 0 → sonnet 5 → opus 9); the
  window templates do (haiku 4/0/0 → sonnet 10/10/9). A template everyone passes (or fails) is wasted
  measurement.
- **M — Moat potential.** Is the answer *not* trivially on the authoritative public web? LOW =
  published fact (a vote value, a current status). HIGH = exact aggregation over large sets, multi-hop
  joins, quote-verification over long documents, cross-source identity — things that need OUR
  corpus/index/joins. (Pass 1/2 calibration: public lookups = LOW; verification-over-scale = the open
  question worth testing.)
- **T — Tier (the doc's curriculum).** 1 single-hop → 2 aggregation → 3 two-table join → 4 multi-hop
  → 5 temporal → 6 adversarial/unanswerable. The doc: tiers 3–6 are "where a general frontier model
  produces fluent, confident, wrong output." Higher tier ⇒ more signal + more moat surface.

**Build rule:** build the **Tier-3+ "fabrication frontier" thin-vertical across families** first;
deepen the easy tiers only when a downstream need appears. Keep the slice cadence (scope → plan →
5-lens panel → work → trust-bar verify); make rigor **proportional to stakes** (full frozen-core
discipline for a template that will train a model; lighter for an exploratory measurement). Keep the
**benchmark** (frozen content) and the **experiments** (the ablation; non-frozen) conceptually
separate — we conflated them.

## Built so far
- **Family 1 (roll-call): all 8 templates** — incl. the discriminating ones (`party_breakdown`,
  window templates). Tier 1–3 of Family 1 is DONE.
- **Family 10 #2 `cite_record_id`** (provenance citation, tier 6).
- **Harness + experiments:** the frozen-core (graders/scoring/trace/hashes/precompute), the live
  AgentSolver (messages-api + agent-sdk backends), the tool-surface ablation (surface knob,
  `fetch_url`, trust-weighted metric, `--template`/kind-axis orchestrator). Reusable.

## The backlog (priority order, with justification)

| # | Template | Fam | T | D | M | Data | Why this priority |
|---|----------|-----|---|---|---|------|-------------------|
| ~~1~~ | ~~Cosponsored bill Y AND voted against it~~ **SHIPPED** | 2 | 3 | H* | M | ✅ | The first Tier-3 cosponsor×vote join. **SHIPPED** (PR, 2026-06-28). *Live discrimination (haiku/sonnet, n=10): sonnet 14/14, haiku 13/14 — D is **cardinality-gated** (near-ceiling on the common |gold|=1 case; separates only on large defector sets — haiku missed 2/8 on the 8-defector bill, a precision-at-scale omission, the predicted join error mode). To use as a STRONG discriminator, oversample high-|gold| bills.* |
| ~~2~~ | ~~Never cosponsor across the aisle~~ **REJECTED** | 2 | 3 | — | — | ✅ | **Scope-review rejected (2026-06-28):** crossing the aisle is the NORM, not the exception (median **56** cross-aisle cosponsorships per member-congress; 89% of cells >15). No ∅ "principled-partisan" population (the 28 never-crossed are low-volume members); set_match needs a thin selection-biased ≤5-cross-aisle gate (2.3% of cells); a count is an exact-large-number lottery. The premise is false in the data — no clean answer shape. |
| ~~3~~ | ~~Most frequent cosponsorship pairs / blocs~~ **TOOL, not task** | 2 | 3 | — | — | ✅ | **Reclassified (2026-06-28):** high USER value + tractable in SQL, but a weak agent EVAL — once the tool does the pairwise co-occurrence, the agent just sorts the output (no reasoning, the cite "answer-in-the-tool" trap). **Build as a product `RESEARCH_TOOL` when there's demand**, not an eval template. See [[project_research_tools_beyond_eval]]. Could feed a richer multi-hop task later (bloc partners -> their votes). |
| — | Lead-sponsor passage rate / Bipartisan count | 2 | 2-3 | M | L | ✅ | Weak (tier-2 aggregations, not sharp joins). **Family 2 declared DONE** — the cosponsor×vote join (#1) was the one strong Tier-3 join; the rest are rejected/weak/tool-not-task. |
| **NEXT** | **Quote-in-bill-text verification (#3)** | 10 | **6** | H | **H** | ⛔ `bill_texts`=68 | **The flagship adversarial-provenance task + the strongest remaining moat candidate** (exact verification of a NEGATIVE over a long document — what web's snippet retrieval can't do). **BLOCKED on a bill-text corpus** (0.05% ingested) + the selection-bias discipline. The natural home for the *resurrected* moat ablation. Scope as a deliberate corpus+template investment, not a quick slice. **NEXT SLICE.** |
| — | Bills sponsored / cosponsored by X | 2 | 1 | L | L | ✅ edges | Single-hop lookup — low on all axes (like `vote_lookup`). Coverage only; deprioritize. |
| 8 | Temporal: point-in-time bill status as of T | 9 | 5 | ? | ? | ⚠ no bitemporal store | High tier, but needs a transaction-time/bitemporal store we don't have. Infra-gated; revisit if we build bitemporal. (Note: point-in-time *party* already tested → no moat; don't assume temporal = moat.) |
| — | Existence check (#1) / refusal calibration (#4) | 10 | 6 | L | L | ✅ | **Skip** — redundant: `cite_record_id`'s no-link arm already proves "X never voted on Y → REFUSE," and every template carries refusal twins. Low marginal value. |
| — | Crosswalk reconciliation (#5) | 10 | — | L | L | ⚠ | **Skip for now** — thin for a federal-only lab (Open States is state legislatures); revisit with a real multi-source identity problem. |
| — | Bill status / actions (Family 3) | 3 | 1-2 | L-M | L | ✅ 981k actions | Data-rich but mostly public single-hop/aggregation. Deprioritize vs the Tier-3 joins. |

## Decisions recorded
- **Family 2 `cosponsored Y AND voted against it` SHIPPED** (PR #43) — the one strong Tier-3 join.
  Chosen for the *reason* (fabrication frontier), not because "Family 2 is next." D is cardinality-gated.
- **Family 2 declared DONE (2026-06-28).** never-cross-aisle REJECTED (crossing is the norm — no clean
  answer shape); blocs is a TOOL not an eval task (build as a product `RESEARCH_TOOL` per
  [[project_research_tools_beyond_eval]]); passage-rate/bipartisan are weak tier-2 aggregations. The
  cosponsor×vote join was the only strong remaining Family 2 Tier-3 join.
- **NEXT = quote-in-text (#3)** — the flagship, paired with the bill-text corpus investment + the next
  moat ablation. Do NOT build the cheap F10 lookups (#1/#4/#5) — redundant/thin.
- **Build product research_tools beyond eval** — capabilities users want (blocs) even when they're poor
  eval tasks; track as a standing workstream ([[project_research_tools_beyond_eval]]).
- **`family9.member_party_at_vote` is NOT promoted** to a trusted benchmark slice until its gold is
  reconciled vs the Clerk record (`2026-06-28-person-party-spans-gold-integrity.md`).
- Re-score after each live run — discrimination is empirical, not a prior.
