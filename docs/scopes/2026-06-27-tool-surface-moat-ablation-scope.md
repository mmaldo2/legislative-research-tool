---
date: 2026-06-27
topic: Tool-surface "moat" ablation — pass 1 (vote_lookup control)
scope-mode: reduce
status: approved
---

# Scope: Tool-surface "moat" ablation — Pass 1 (vote_lookup control)

## Problem
As frontier base models commoditize, the existential question for a domain-specialized product is
**"how much of a correct, trustworthy answer is the model vs. our tools/data layer?"** The ablation
promotes **tool-surface** to a first-class experimental axis (model × surface), reframing the
benchmark from "rank models" to "measure the moat." Pass 1 is the deliberate **control**: prove the
harness + the trust-weighted metric are sound on a case where we *expect no moat*, before betting on
the arenas where we expect one. (Decisions: scope-review + design-chat, 2026-06-27.)

## In Scope (pass 1 — vote_lookup CONTROL)
- **Arena:** `vote_lookup`, **answerable arm only**, the **frozen template reused unchanged** (identical
  prompt to both surfaces → pure harness experiment; the internal roll-call id is semi-parseable and
  the same for both). **No synthetic-id refusal twins** (they telegraph fakeness → under-test web
  over-claiming; deferred to a real-member no-link in pass 2).
- **Matrix:** surface {ours, web} × model {haiku, sonnet} = **4 cells**. `ours`-vs-`web` (model held
  constant) isolates the tool effect; haiku+ours vs sonnet+web is the money cell.
- **Backend held constant = `agent-sdk`** (surface is the SOLE variable; the web arm *requires* it —
  Claude Code has WebSearch/WebFetch; the messages-api loop has only our tools). vote_lookup results
  are tiny → no opus-style offload confound.
- **Surface mechanism (minimal):** a per-surface allow/disallow toggle. `ours` = today's lockdown;
  `web` = WebSearch/WebFetch + submit_answer only (filesystem/shell STILL blocked — integrity).
- **Separate ablation orchestrator** (a new lab module): owns the cell matrix + the **trust-weighted
  report** — accuracy / hallucination (confident-wrong) / over-refusal, **3 rates PER surface,
  separately** (not one aggregate; raw accuracy hides the moat). Reuses `AgentSolver`.
- **Web = moving baseline:** run N× per web cell, report variance; the `ours` cells stay the
  reproducible spine.
- **Expected result: a TIE (no moat on simple lookups).** A spurious moat here = a broken metric.

## Out of Scope (deferred)
- Pass 2 moat-revealing arenas: `party_breakdown`/`crossed` (point-in-time party — web gives current
  party, wrong on switchers) + a **real-member-real-bill-no-vote** over-claim probe (the Family 10
  structurally-disjoint no-link, NOT a synthetic id).
- `both`/`neither` surfaces; the cite "product-demonstration" (ontology-loaded → separate framing).
- The compute-over-tool-outputs sandbox (separate integrity-only `_DISALLOWED_BUILTINS` refactor).
- Any frozen-core change (graders/scoring/vocab/templates) — STOP-and-surface if one seems needed.

## Key Constraints
- Reuses the frozen `vote_lookup` template + the existing graders/scoring + `AgentSolver` wholesale;
  `grading_contract_hash` + `content_hash` UNMOVED (no template/grader change — pure harness/runner).
- Integrity invariant: web may reach Congress.gov (a legitimate alt source) but NEVER our DB/gold
  (not web-published) or the filesystem/shell.

## Codebase Context
- `lab/solvers.py`: `AgentSolver` (agent-sdk backend, `_asolve_sdk`), `_DISALLOWED_BUILTINS` (the
  lockdown to make per-surface configurable), `_make_sdk_product_tool`, `allowed_tools` wiring.
- `lab/run.py`: the existing single-template runner + fairness diagnostics (the report to NOT muddy).
- `lab/graders.py` / `scoring.py`: the `decision_correct` / `answer_correct` / refusal subscores the
  trust-weighted rates derive from. Memory: [[project_condorcet_eval_philosophy]].

## Open Questions (for /ce:plan)
1. Exact trust-weighted rate definitions from the existing subscores (hallucination = answerable &
   decision_correct=1 & answer_correct=0? over-refusal = answerable & refused?).
2. The surface-toggle shape on `AgentSolver` (a `surface` param → allow/disallow + tool provisioning).
3. Web-arm observation capture (WebSearch/WebFetch calls into the trajectory for the trust bar).
4. The orchestrator's module shape + how it emits the per-surface 3-rate comparison table + variance.
