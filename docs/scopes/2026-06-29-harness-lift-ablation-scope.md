---
date: 2026-06-29
topic: Harness-lift ablation over the existing suite (the re-score outcome)
scope-mode: expand
status: approved
---

# Scope: Harness-lift ablation (re-score outcome)

## Problem
The eval's job is no longer to find a task that defeats the FRONTIER (a dead end on public data --
3 findings) but to **demonstrate harness LIFT** while staying a defensible public good. Per the
finalized design [[project_condorcet_experimental_design]], the unit of measurement is the ablation
**S+H vs S+T** (model fixed, isolates the harness) with **S+H vs F+T** as the cost/capability
headline. We already have the TASK substrate; we lack the measurement apparatus. So the re-score
REDIRECTS the build from "new task families" to "the lift ablation over the existing suite."

## In Scope
- **DONE (branch feat/lab-baseline-code-exec):** the honest baseline `surface="web"` is now
  **web + code** -- a guarded `run_python` (`python -I -S`, stdlib-only -> no DB driver -> can't reach
  our Postgres; scrubbed env; time/output caps). The baseline can now compute, not just retrieve.
- **The lift run:** execute S+H (surface=ours) / S+T (surface=web) / F+T over the EXISTING suite
  (tally, party_breakdown, covoting, the cosponsor/window joins) via `--backend agent-sdk`, models
  held fixed for the ablation; exclude truncations (max-turns/budget probed first); compute
  **lift = S+H - S+T** per task + the **S+H >= F+T** punch-up. (Lift instrumentation: add the
  per-rollout symmetric-diff/pass already specified for the screen, or a post-hoc jsonl pass.)
- **Empirically tier** each task: demonstration (lift real -> S+H wins, S+T/F+T fray on
  completeness/scale) vs research-frontier (S+H also fails -> harness-R&D / RLVR headroom).

## Out of Scope
- New task families (we have enough substrate; prove lift on it first).
- Reverse-engineering tasks from our tool surface; weakening the baseline (the bias bright lines).
- A published-grade baseline sandbox (OS network-isolation + security-sentinel) -- experiment-grade
  `run_python` is enough to MEASURE now; harden before publishing numbers.

## Key Constraints
- Defensibility: PUBLIC = tasks + gold + the Agent-SDK baseline scaffold + methodology; PROPRIETARY
  = the harness, the traces, the weights. Baseline must stay strong + honest (pre-registered).
- Frozen `grading_contract_hash` UNMOVED (no grader change); the ablation lives in lab/solvers.py +
  run/analysis code (neither hash). Read traces (trust bar) -- esp. confirm no S+T rollout reached
  our DB via run_python.

## Codebase Context
- Ablation infra revived + reframed from "moat" to "lift": `lab/solvers.py` surfaces
  (`ours`/`web`), `AgentSolver(surface=...)`, the run-loop in `lab/run.py` (+ the `--max-turns`/
  `--max-budget-usd` passthrough from PR #47). The paused pass-1/2 moat harness is the starting point.

## Open Questions (for /ce:plan)
1. Which models for S / F (e.g. S=haiku or sonnet; F=opus)? The headline #1 is small+harness ~= F+T.
2. Budget/turn probe + truncation-exclusion protocol (reuse the screen-hardening: probe cost, set
   cap ~3x, exclude non-success); does `run.py` need a multi-surface/multi-model batch driver?
3. Lift metric: per-task pass-rate delta + symmetric-diff distribution; the demonstration-vs-research
   tier cutoff, pre-registered.
4. F+H (goal #2) now or later.
