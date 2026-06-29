---
date: 2026-06-28
topic: family10.quote_in_bill_text (Slice B) — adversarial verbatim-quote verification
scope-mode: reduce
status: deprioritized (discrimination gate failed 2026-06-28; do not build)
---

# Scope: family10.quote_in_bill_text (Slice B)

## Problem
The flagship Tier-6 provenance task: given a bill and N candidate quotes, the agent must return exactly which are **verbatim** in the bill text and refuse the un-answerable — "exact verification of a negative over a long document." Justified by **discrimination + RLVR training signal** (the verbatim-verification fabrication-frontier skill), NOT moat (see Out of Scope). Runs over the Slice-A corpus (`bill_texts`: 11,833 119th HR+S introduced rows).

## In Scope
- **Probe FIRST (a hard gate, before any build):** ~6-10 hand-built verbatim-vs-near-miss items over real corpus bills, run haiku/sonnet/opus; read traces. **Proceed only if models actually discriminate**; if everyone aces it, STOP and reconsider (it would be `vote_lookup`-class).
- Frozen template `family10.quote_in_bill_text`: **`set_match` over candidate-quote-ids** (gold = the verbatim subset; ∅ valid), identical prompt shape for positives + negatives, `refusal_correct` twins (nonexistent / un-corpused bill). Mirrors `cite_record_id`.
- **Deterministic adversarial-negative generator** (reproducible, NOT LLM-at-eval-time): positives = real verbatim spans from the bill; negatives = single-token deterministic alterations of real spans (number / defined-term swap) and/or cross-bill real spans.
- New `get_bill_text(bill_id)` RESEARCH_TOOL returning the full `content_text` (mirror `get_bill_cosponsors`); the agent fetches + verifies. Restrict task bills to a text-length budget (tool-output cap).
- Seam wiring (`SUBMIT_SCHEMAS` / `SET_MATCH_FIELD` / `TEMPLATE_TOOLS`), oracle/wrong/over-refuse invariants, hermetic + `requires_pg` tests, and a haiku/sonnet/opus discrimination run.

## Out of Scope
- **The tool-surface "moat" ablation** — DEFERRED to a separate skeptical follow-up. The corpus is public web text (congress.gov/govinfo), so a `fetch_url`-armed web agent has the same text and can verbatim-check it -> likely replicates the pass-1/2 NO-MOAT finding. Don't bundle; don't tune to manufacture a moat ([[project_condorcet_eval_philosophy]]).
- **`exact` / extraction answer shapes** — `exact`'s format gate is vote-options-only; `set_match` is the only frozen-compatible shape.
- New grader modes; LLM-generated-at-eval-time negatives (non-reproducible); non-introduced / multi-congress text.

## Key Constraints
- Frozen `grading_contract_hash` **UNMOVED** (no `graders.py`/`scoring.py`/vote-parser change); `content_hash` legitimately moves (templates.py grows) — the `cite_record_id` precedent.
- "Verbatim" is decided at **gold-construction time** via a fixed normalization (whitespace canonicalization), NOT in the grader (graders compare id-sets only).
- Candidate-quote-ids must be stable + **leak-safe** (the id must not encode whether it's verbatim).

## Codebase Context
- Sibling: `lab/templates.py::generate_cite_record_id` (set_match singleton + refusal twins, per-emit proofs). Seam: `lab/solvers.py` (`SUBMIT_SCHEMAS`/`SET_MATCH_FIELD`/`TEMPLATE_TOOLS`, `lab_execute_tool`). Tool pattern: `get_bill_cosponsors` (`src/api/chat.py` + `src/llm/tools.py`). Corpus: `bill_texts.content_text` (clean) + `content_xml`. Frozen graders: `lab/graders.py`.

## Gate status (2026-06-28) — FAILED. Task DEPRIORITIZED (do not build).
The discrimination probe was the gate. **HARDER probe (3 long bills up to 7,500 words; 21 candidates =
12 verbatim + 9 deep near-misses: numbers incremented inside U.S.C. citation chains, `shall->may`
buried mid-clause): haiku scored 21/21 (bills-exact 3/3, near-miss caught 9/9, verbatim found 12/12).**
The pre-registered go bar was a gradient haiku < sonnet < opus on near-miss exclusion; **haiku ceilings
it, so no gradient is possible** -- sonnet/opus (rate-limited out anyway) cannot exceed perfect.
Verbatim verification with the text available is substring search; modern models do it flawlessly (the
"answer-is-in-the-tool" triviality flagged above, confirmed). **VERDICT: NO-GO -- deprioritize the
flagship, re-score the backlog. Slice A corpus retains product value and is available if a genuinely
discriminating quote-task design ever emerges (extraction is blocked by the vote-only `exact` grader).**
Probe scaffold: `lab/experiments/quote_discrimination_probe.py`.

## Open Questions (for /ce:plan)
1. Probe design: item count, scoring (manual trace-read vs the lab harness), and the explicit go/no-go bar.
2. Negative recipe: single-token alteration vs cross-bill vs both; candidates-per-item; positive:negative ratio.
3. "Verbatim" normalization: the exact canonical form (whitespace/case/punctuation) that is well-defined yet not brittle given the newline-fragmented corpus text.
4. `get_bill_text` shape + the per-bill length cap (tool-output budget); how task bills are selected within it.
5. Candidate-id minting: stable, leak-safe scheme.
