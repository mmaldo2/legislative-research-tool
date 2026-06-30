---
date: 2026-06-29
topic: harness-lift full matrix run + paired analysis
scope-mode: selective-expand
status: approved
---

# Scope: Harness-lift full matrix run + paired analysis

## Problem
The egress-isolation gate is merged (PR #53, main @ f0bafd3), so the harness-lift comparison can now
produce DEFENSIBLE headline numbers. We have the matrix driver + lift suite + isolated gate; we lack
(a) the powered, pre-registered run and (b) the paired cost/reliability/parity analysis.

## In Scope
- **Staged execution** (de-risk the spend like the Phase-3 probe):
  1. `lift_pairwise` live validation — roster/cast spotcheck vs the Clerk (mirror `lift_roster_spotcheck.py`) + a tiny n=2-3 both-arms smoke (pairwise has NEVER run live).
  2. All-5-cells SMOKE: haiku+sonnet x {ours,web} + opus x web, n=6, k=1, BOTH templates (~$15) -> read discordance + per-cell cost/latency.
  3. PRE-REGISTRATION (REV 4.5) commit: pin n, model snapshots, seed, k, parity band, excluded subtypes; record the doc hash BEFORE the powered run.
  4. POWERED run sized to the smoke evidence (k>=3; n set by whether discordance exists).
- **New paired-analysis script** (`lab/experiments/lift_analysis.py`, reads `ablation_*.jsonl`, NO harness change): pair by `instance_id` across surface within model; per (model,template) report 3-rate, paired **McNemar** (ours vs web accuracy), **cost ratio + CIs** (Wilson for rates, bootstrap for cost), variance across k reps; EXCLUDE `result_subtype in {sandbox_infra}` + errored. Emit **lift = S+H - S+T** (per model) and **punch-up S+H vs F+T**.
- **Arms:** haiku+sonnet x {ours (S+H), web (S+T)} + opus x web (F+T). The always-on S+T control IS the same agent-sdk web surface (no separate build).

## Out of Scope
- **F+H (opus x ours)** — secondary goal #2; skip this round (cost; headline #1 needs only S+H/S+T/F+T).
- New templates/families; any frozen-core change (lift instances are non-frozen; `solvers.py` unchanged).
- DB-cred rotation — deferred defense-in-depth; the `--network none` gate already blocks the path.
- Re-running the merged Phase-3 numbers as "the smoke" — the smoke adds the missing cells (small x web).

## Key Constraints
- **Billable**; opus x web + sonnet x web dominate. The staged smoke bounds the envelope before powering up.
- **McNemar needs DISCORDANT pairs.** Phase 3 = 100%/100% on member_summary (opus x web). If the small x web cells also ceiling -> no accuracy signal -> headline pivots fully to COST/RELIABILITY and a small n suffices (the REV 4.4 reframe).
- **Pre-registration discipline**: commit the pinned parameters + doc hash before the powered run (anti-cheat + credibility).
- Run **SEQUENTIALLY** (the `ANTHROPIC_API_KEY` pop is process-global; ablation.py already enforces) on **agent-sdk** (subscription, no rate wall).

## Codebase Context
- `lab/ablation.py` — the matrix driver; extend its CLI invocation (models/surfaces/templates/n/seed/repeats), already routes `sandbox_infra` -> excluded, writes `ablation_{model}_{surface}_{kind}_{ts}.jsonl`.
- `lab/experiments/lift_instances.py` — both templates ready (`lift_member_summary` validated; `lift_pairwise` gold-mirrored, UNSMOKED).
- `lab/experiments/lift_roster_spotcheck.py` — the read-only cast-level Clerk-check pattern to mirror for pairwise.
- Trace rows carry `policy.surface/model` + `verdict.subscores` + `cost` + `result_subtype` + tokens -> the analysis script reads traces only.

## Open Questions
- Exact stats: exact-binomial McNemar for small discordant n? Wilson (rates) + bootstrap (cost ratio) CIs — confirm in plan.
- The powered n/k **decision rule** from the smoke (e.g. discordance >= X -> power to n=N; else fix n small + report cost/reliability).
- Does `lift_pairwise` need its own gold-vs-Clerk reconciliation, or does the member-level 40/40 spotcheck transfer?
