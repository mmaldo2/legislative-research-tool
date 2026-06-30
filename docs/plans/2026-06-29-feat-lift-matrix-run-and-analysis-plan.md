---
title: "feat(lab): harness-lift full matrix run + paired analysis (lift_analysis.py)"
type: feat
status: active
date: 2026-06-29
origin: docs/scopes/2026-06-29-harness-lift-full-matrix-scope.md
---

# feat(lab): harness-lift full matrix run + paired analysis

## Overview
The egress-isolation integrity gate is merged (PR #53, main @ f0bafd3). The harness-lift comparison
can now produce DEFENSIBLE headline numbers. We have the matrix driver (`lab/ablation.py`), both lift
templates (`lab/experiments/lift_instances.py`), and the isolated `run_python`/`fetch_url` conduits.
We lack: (1) a **paired statistical analysis** of the trace output, and (2) the **powered,
pre-registered run** that feeds it. This plan builds the analysis script + a small manifest/run-id
extension to ablation.py, then executes the run in STAGES (validate cheap → pin n → spend) and updates
the pre-registration (REV 4.5). See [[project_condorcet_experimental_design]] (the arms / headline)
and the existing pre-registration `docs/plans/2026-06-29-feat-lab-harness-lift-ablation-plan.md`
(rev 4 — n=40, seed=42, the 5 cells, k=3, exclusion rule, metrics).

## Problem Statement
`ablation.py` runs the surface×model matrix and prints per-cell rates + a web−ours delta + min/max
over repeats. That is NOT the headline. The pre-registered claim is **cost + reliability at accuracy
PARITY** (REV 4.4), which requires PAIRED statistics the driver does not compute: a paired accuracy
equivalence interval (not a mean), a bootstrap cost-ratio CI (cost is right-skewed), and a
completion/reliability decomposition. There is **no McNemar/Wilson/Newcombe/bootstrap code** in the
repo (`numpy` is available; `scipy`/`statsmodels` are NOT). Separately, the powered run is billable
(opus×web + sonnet×web dominate; ~$300-450 at n=40, k=3, 2 templates), and `lift_pairwise` has NEVER
run live (gold-mirrored but unvalidated). Spending before validating the apparatus + the small×web
cells (which have never run under the new fetch-to-mount gate) would be premature.

## Proposed Solution
1. **`lab/experiments/lift_analysis.py`** — a NON-FROZEN, trace-reading analysis script (zero harness
   change for data capture; the trace already carries `policy.surface/model`, `verdict.subscores`,
   `cost`, `result_subtype`, tokens). It pairs by `instance_id` across surface within model and
   computes the pre-registered metrics with the exact small-N statistics (hand-rolled, stdlib+numpy):
   exact McNemar, Wilson, Newcombe paired-difference CI, paired cluster-bootstrap cost-ratio,
   completion/flip-rate, Holm. Emits a printed report + a JSON artifact (the pre-reg record).
2. **Minimal `ablation.py` extension** (non-frozen): `--run-id <tag>` (tags the per-cell output
   filenames + writes a `manifest_<tag>.json` recording the pinned params + the list of cell files +
   the pre-reg doc git hash), and `--template a,b` (loop templates). This gives `lift_analysis` a
   deterministic, provenance-stamped set of files to read (NOT a fragile timestamp glob).
3. **Staged execution** (de-risk the spend, mirroring the Phase-3 probe):
   - Phase 1: build the analysis + manifest plumbing (no spend; hermetic + a tiny live smoke).
   - Phase 2: validate `lift_pairwise` live + the n=6/k=1 all-cells SMOKE (~$15) → run `lift_analysis`
     on it → read discordance + the real per-cell cost envelope. STOP, present.
   - Phase 3: REV 4.5 pre-registration commit (confirm/adjust n + Δ from smoke evidence; pin the exact
     stat variants + the analysis-script + manifest contract; commit the doc hash) → the POWERED run →
     `lift_analysis` → write-up.

## Technical Approach

### Architecture — the data flow (no new capture path; the trace IS the substrate)
```
ablation.run_matrix(templates, models, surfaces, n, seed, repeats, run_id, prereg_sha)
    | loops the validated single-template run_ablation per template (preserves its per-template summary)
    | per cell (model x surface x kind x rep): solve_grade_write -> per-instance trace rows
    | writes RUNS_DIR/ablation_<run_id>_<model>_<surface>_<kind>_<ts>.jsonl  (k files per cell = reps)
    | writes RUNS_DIR/manifest_<run_id>.json (Pydantic RunManifest; params+hashes+prereg_sha AT START,
    |   cell_files[] APPENDED as each cell completes -> crash-safe)
    v
lift_analysis.analyze(run_id)
    | read manifest -> load ONLY this run's cell_files; ASSERT hash-homogeneity across all rows
    |   (mixed grading_contract_hash / content_hash / dataset_fingerprint -> hard error: catches a
    |    smoke file mixed with a powered file, since gold is computed vs a MUTATING live DB) (review M1)
    | group by (template_id, model[FULL id e.g. claude-haiku-4-5], surface)  (review L10)
    | pair by instance_id with ARBITRARY (model,surface) arms (primary S+H-vs-F+T pairs across BOTH
    |   model AND surface; secondary S+H-vs-S+T pairs within model) -- valid: instances generated once,
    |   reused across cells (review L3). ASSERT the paired answerable id-sets are IDENTICAL per arm-pair;
    |   report any singleton as a drop (do NOT silently inner-join) (review M7).
    | aggregate k reps -> per-instance outcome (majority-vote; post-exclusion tie -> incorrect)
    | EXCLUDE result_subtype not in {"success"} from the conditional population (a MISSING/None subtype
    |   on the agent-sdk arm = errored/timeout = non-success -> excluded here, scored WRONG in ITT)
    |   (review L11); KEEP every rollout for the completion-rate denominator
    v
per (template, model-pair) report:
    - accuracy: exact McNemar (b,c) + Newcombe paired-diff CI vs margin Delta  [primary: S+H vs F+T]
    - reliability: completion-rate (Wilson) | conditional acc | ITT acc; flip-rate  [the headline gap]
    - cost: paired cluster-bootstrap ratio CI + median/IQR + geometric-mean ratio
    - 3-rate split (accuracy / hallucination / over-refusal) on the answerable arm
    - secondary diagnostic: S+H - S+T controlled lift (same model, paired)
    -> printed table + RUNS_DIR/lift_analysis_<run_id>.json
```

### The statistics (hand-rolled; stdlib `math`/`statistics` + `numpy`; NO scipy). Pure -> hermetic tests.
Methods + formulas are from the best-practices research (citations in Sources). Posture:
**estimation-first** — the CI is the result; p-values are secondary (Card et al. 2020, small-N power).

- `mcnemar_exact(b, c) -> (p, note)` — two-sided exact binomial on the discordant pairs:
  `p = min(1, 2 * sum(C(n,i) for i in 0..min(b,c)) * 0.5**n)`, `n=b+c`. **b=c=0 -> "0 discordant,
  not applicable", pivot to the CI.** (Exact, not chi-square: b+c < 25 at our N.)
- `wilson(x, n, z=1.96) -> (lo, hi)` — score interval for a single proportion (per-arm accuracy /
  completion). NEVER Wald (zero-width at the p̂=1 ceiling).
- `newcombe_paired(a, b, c, d, z=1.96) -> (lo, hi)` — Newcombe (1998) method 10 paired-difference CI
  (square-and-add of two Wilson intervals + the φ̂ correlation correction). Degrades gracefully at the
  boundary; this is the PARITY interval. **Highest numerical risk (review H2): pin MULTIPLE oracles
  from the Newcombe 1998 paper itself** (not one self-authored value) — a symmetric table, a boundary
  table with a zero margin (a=0 or d=0, where φ̂'s denominator degenerates), and the b=c=0 degenerate —
  one oracle can't catch a sign error in the correction term.
- `boot_ratio_ci(costA, costB, B=10000, rng) -> (lo, hi, median)` — paired cluster bootstrap:
  resample QUESTIONS with replacement (SAME index set both arms; `numpy.random.default_rng(seed)`,
  NOT legacy `np.random.seed`; B index arrays drawn vectorized), recompute mean(A)/mean(B), percentile
  CI. **This bootstrap CI is THE single pre-registered primary cost statistic** (review: don't triple-
  report). ALSO report per-question median+IQR as the honest robust summary. Geometric-mean ratio is an
  OPTIONAL sensitivity line only (not a co-equal headline — forking-paths risk at small N). **Cost
  exclusion is PAIRWISE** (review H3): drop instance i from the cost vectors if EITHER arm has
  `cost is None`, keeping costA/costB index-aligned; guard `mean(B)==0` (skip that resample draw / the
  empty-vector case); report the pairwise cost-coverage fraction.
- `completion_flip(rows_by_instance) -> {completion, flip_rate, ...}` — completion = gradeable /
  total rollouts (Wilson CI; guard n=0); flip-rate = non-unanimous questions / N.
- ~~`holm(...)`~~ **DEFERRED (review: simplicity).** Holm exists only to support a family-wise "wins
  everywhere" claim nobody has committed to. The pre-registered PRIMARY endpoint is single -> no
  multiplicity to correct. Report all comparisons with CIs; add Holm (~8 lines, hermetic) ONLY if a
  reviewer later presses for the global claim. Keeps the registered analysis to the endpoints we defend.

### k reps -> one outcome per question BEFORE McNemar (avoid pseudo-replication)
Aggregate each instance's k reps to **majority-vote correct** for the binary McNemar; report rep
variance / flip-rate SEPARATELY as reliability (majority-vote hides brittleness -> flip-rate restores
it). Do NOT feed 3·N rows into McNemar (fakes the sample size). **Tie rule (review M8):** k=3 is
tie-free ONLY at full reps, but the conditional population keeps instances answered on >=1 of k, so
after excluding non-`success` reps an instance can have 2 gradeable reps that split 1-1 -> pin the
rule: a post-exclusion tie counts as INCORRECT for the conservative McNemar (and a fixture covers the
variable-rep-count case). GLMM/GEE rejected at N<=40 (separation / small-cluster sandwich bias) -> the
cluster bootstrap is the robust substitute.

### Reliability decomposition (the headline-defensible part; maps onto the pre-reg's bounded interval)
Report THREE panels per (arm, template), never folding truncation into accuracy:
1. **Completion rate** (Wilson CI) — gradeable rollouts / total.
2. **Conditional accuracy** = the complete-case McNemar (paired population = instances both arms
   answered on >=1 of k) = the pre-reg's `exclude-truncation` bound. Labeled "conditional on answering."
3. **ITT accuracy** = score every truncation/error as WRONG, McNemar/Wilson on the full N = the
   pre-reg's `count-truncation-as-miss` bound.
The **conditional-vs-ITT gap** is the reliability headline: if S+H ties S+T on conditional accuracy but
completes more often, ITT favors S+H and the difference is purely reliability — tied to the cost thesis.

### Pairwise live validation (answers scope open-Q3: does pairwise need its own Clerk reconcile?)
The member-level 40/40 cast spotcheck validated the per-(member, roll) OPTION data. Pairwise gold is a
deterministic JOIN over those same casts -> it needs (a) a **join-logic cross-check** (recompute
`_pairwise_gold` independently in Python from each member's full record diff; assert == the SQL, a few
seeded pairs) and (b) **extend `lift_roster_spotcheck.py` to the pairwise members' casts** for 2-3
pairs (live, cheap; members not in the original 5 add coverage). NO separate full Clerk reconciliation
is required — the join is deterministic over already-validated casts.

### New files / changes (named)
- **`lab/experiments/lift_analysis.py`** (new) — the stat functions (Holm deferred) + PURE helpers
  decomposed for testability (review M9, mirroring ablation's `_agg`/`_delta` granularity):
  `load_run(manifest)`, `pair_by_instance(rows)`, `build_2x2(paired) -> (a,b,c,d)`,
  `cost_vectors(paired)`, `three_rate_split(paired)`, then `analyze(run_id)` just orchestrates +
  `_print_report` + `main(argv)` CLI (`--run-id`, `--delta`, `--bootstrap-iters`, `--bootstrap-seed`).
  Reads `RUNS_DIR/manifest_<run_id>.json`. Splits answerable vs refusal via the row's `is_refusal`
  field, NOT a `:refusal:` id substring (review M7).
- **`lab/manifest.py`** (new, tiny) — a shared **Pydantic** `RunManifest` model (the lab already models
  persisted contracts with Pydantic: `TraceRecord`/`RunContext`) so ablation (writer) and lift_analysis
  (reader) reference ONE schema, not a hand-rolled dict on each side (review arch-M5). Fields:
  `run_id, params, rollout_seed, prereg_doc_sha, grading_contract_hash, content_hash,
  dataset_fingerprint, cell_files[]`.
- **`tests/test_lab/test_lift_analysis.py`** (new) — hermetic stat tests pinned to PUBLISHED oracles:
  `mcnemar_exact` (4,0)=0.125, (b=c) clips to 1.0, (8,0); **multiple Newcombe oracles from the 1998
  paper** incl. a zero-margin boundary + the b=c=0 degenerate; `wilson` edge p̂=1 non-zero width +
  n=0 guard; bootstrap on a skewed fixture (+ pairwise cost-exclusion alignment + mean(B)=0 guard) +
  flip-rate. PLUS a synthetic-trace fixture exercising pairing, set-equality assert, exclusion,
  conditional-vs-ITT, the post-exclusion 1-1 tie, cost=None pairwise drop, and **a pinned report-JSON
  top-level key set** (the artifact IS the pre-reg record; a refactor must not silently reshape it —
  review L13).
- **`lab/experiments/lift_pairwise_validate.py`** (new, READ-ONLY) — the **join-logic cross-check**
  (independent Python recompute of `_pairwise_gold` from each member's full record diff == the SQL,
  seeded pairs) as the gate, PLUS at most ONE sanity cast pair (review: trimmed — the recompute already
  reads the casts; don't build a parallel mini-spotcheck). No separate full Clerk reconciliation.
- **`lab/solvers.py`** (MODIFY, non-frozen, NOT in either hash) — **cost-capture fallback (review
  H1/C1):** in `_asolve_sdk`, also capture `ResultMessage.usage` -> populate `input_tokens`/
  `output_tokens` in `extras` (the trace schema already has the slots; the SDK path never fills them).
  So if `total_cost_usd` is null under subscription auth, a token x public-price cost proxy exists.
  (Empirically the merged Phase-3 pilots DID report real `total_cost_usd` — $0.16/$0.60/$1.26 — so this
  is INSURANCE, not a known gap; the smoke gates it, see Phase 1/2.)
- **`lab/ablation.py`** (MODIFY, non-frozen) — add `--run-id`, `--prereg-sha` (explicit, auditable —
  NOT an auto `git rev-parse HEAD`; review arch-H2), and `--template a,b`. Thread `run_id` into
  `_run_cell` and have it RETURN its `out_path` (review M5/arch-M4 — the microsecond-stamped path is
  known only after the cell runs). Add a thin `run_matrix(templates, ..., run_id)` orchestration layer
  that loops the validated single-template `run_ablation` per template, collects cell paths, and writes
  the ONE `manifest_<run_id>.json` (review M6/arch-M3 — a per-run manifest can't live inside the
  single-template `run_ablation`). Write the manifest param block + hashes + prereg_sha AT START and
  APPEND `cell_files[]` as each cell completes (crash-safe: a late failure in a ~$300-450 run still
  leaves an analyzable partial manifest — review arch-M2). No change to `classify`/`_run_cell` scoring;
  SEQUENTIAL. Frozen hashes structurally unaffected (file not in either list — see below).
- **`docs/plans/2026-06-29-feat-lab-harness-lift-ablation-plan.md`** (MODIFY) — append **REV 4.5**
  (confirm/adjust n + Δ; pin the exact stat variants + the analysis-script + manifest contract; record
  the as-run caps from REV 4.4; pin the single primary cost statistic + bootstrap seed in the analysis
  JSON, the rollout seed in the manifest — two distinct seeds, review H4/L1). Commit the doc; its git
  SHA is passed via `--prereg-sha` and stamped in the manifest (the pre-registration anchor).

### Implementation Phases

#### Phase 1: Analysis script + manifest plumbing + cost-capture fallback (no real spend) — DONE
- [x] `lab/manifest.py`: the shared Pydantic `RunManifest` model (one schema, both sides); crash-safe
      `save`/`stamp_hashes`/`add_cell`/`load`.
- [x] `lift_analysis.py`: the stat functions (Holm deferred) + the PURE helpers (`pair_by_instance`,
      `build_2x2`, `cost_vectors`, `three_rate_split`/`arm_summary`) + `analyze` orchestrator + report.
      Asserts hash-homogeneity + reports paired singletons; EXCLUDEs non-`success` (incl. None) from the
      conditional population; computes BOTH conditional + ITT; PAIRWISE cost exclusion + coverage;
      copies `{grading_contract_hash, content_hash, dataset_fingerprint, prereg_doc_sha,
      bootstrap_seed}` into `lift_analysis_<run_id>.json`.
- [x] `solvers.py`: `_usage_tokens` + populate `input_tokens`/`output_tokens` from `ResultMessage.usage`
      in `_asolve_sdk` extras (the token-based cost fallback; additive, hash-safe).
- [x] `ablation.py`: `--run-id` + `--prereg-sha` + comma `--template`; `_run_cell` returns `out_path`;
      `run_matrix` orchestration writing the crash-safe incremental `manifest_<id>.json`.
- [x] `test_lift_analysis.py` (15) + `test_manifest.py` (3): hermetic stat tests on the PUBLISHED
      Newcombe oracle (+ φ-sign-catching asymmetric case) + McNemar power-wall + the synthetic-trace
      fixture (pairing/set-equality/exclusion/conditional-vs-ITT/1-1 tie/cost=None/pinned report-JSON
      keys/mixed-hash rejection). Frozen-hash guarantee is STRUCTURAL: the changed files are in NEITHER
      hash's file list (none of scoring/graders/templates/generate/precompute touched). 282 lab green.
- [x] LIVE plumbing smoke `--run-id smoke0` (haiku ours+web n=2): manifest_smoke0.json written (2
      tagged cell files, ctx hashes stamped); `lift_analysis --run-id smoke0` read it, asserted
      hash-homogeneity, and produced the report. **Cost-coverage go/no-go PASSES**: haiku|ours
      `cost_src={real:2}` (real `total_cost_usd`; the token fallback was not needed, confirming
      Phase-3's empirical finding). Conditional-vs-ITT, pairwise cost exclusion (the errored web
      rollout -> `missing`, dropped), and Newcombe parity ("inconclusive" at n=2) all validated on
      live traces. `ruff` clean; 282 lab green.

#### Phase 2: pairwise validation + all-cells smoke + read discordance/cost — STOP for review
- [ ] `lift_pairwise_validate.py`: the join-logic cross-check (Python recompute == `_pairwise_gold`,
      seeded pairs) is the GATE + at most ONE sanity cast pair (review-trimmed). Must pass before
      pairwise enters a run.
- [ ] All-cells SMOKE: `ablation --run-id smoke1 --template lift_member_summary,lift_pairwise
      --models haiku,sonnet,opus --surfaces ours,web` at n=6, repeats=1 — BUT only the pre-registered
      cells (haiku/sonnet×{ours,web} + opus×web; opus×ours is goal #2, NOT run). ~$15. Sequential,
      agent-sdk. Mechanical trace-grep clean (the integrity tripwire).
- [ ] `lift_analysis --run-id smoke1` -> read: (a) discordance in the small×web cells (the lift
      signal), (b) real per-cell cost/latency -> the n=40 envelope, (c) **cost coverage** (the primary
      endpoint's go/no-go — blocking if subscription cost is null and the token fallback didn't fire),
      (d) any cell that errors/over-refuses systematically. NOTE: `run_ablation` runs the ANSWERABLE arm
      only (`ablation.py:188` filters `is_refusal`), so over-refusal is read from the answerable arm
      (`classify` -> `decision_correct==0`), NOT from refusal twins (which never reach a trace unless the
      filter changes — review arch-M6). PRESENT: the smoke report + a proposed REV 4.5 (n, Δ, budget
      ceiling) decision.

  **The smoke -> power DECISION RULE (resolves scope open-Q2):**
  - If discordant pairs ~0 across all cells (all ceiling, as Phase 3 hinted): accuracy is uninformative
    -> headline is COST + RELIABILITY; n can be MODEST (pre-reg n=40 may be reduced to e.g. n=15-20 for
    a tight enough cost-ratio CI) — REV 4.5 re-pins n DOWN, saving ~$200.
  - If meaningful discordance appears (e.g. haiku×web << haiku×ours): there IS an accuracy lift to
    power; keep n>=40 (or size so expected b+c gives McNemar a chance: b+c>=6 is the FLOOR for any
    p<0.05). Cap by a pre-registered $ ceiling; if 40 is unaffordable, pin the largest affordable n and
    report the power limitation honestly.
  - Either branch: pin the FINAL n + Δ in REV 4.5 BEFORE any powered cell runs.

#### Phase 3: Pre-registration (REV 4.5) + powered run + analysis + write-up
- [ ] **REV 4.5 commit (pre-registration; FROZEN before any powered cell):** confirm/adjust n + Δ from
      the smoke; pin the exact stat variants (exact McNemar, Newcombe method-10, Wilson, paired
      cluster-bootstrap B=10000 + seed, Holm-secondary-only, majority-vote rep aggregation); pin the
      primary endpoint (cost ratio at accuracy parity, S+H vs F+T, on a designated primary cell);
      record the AS-RUN caps (REV 4.4: web turns=30, budget=$3.5, timeout=300s, fetch cap=32MB, mem=2g);
      reference `lift_analysis.py` + the manifest contract. Commit; the SHA is the anchor (also stamped
      into `manifest_<id>.json`).
- [ ] **Powered run:** `ablation --run-id pre45 --template lift_member_summary,lift_pairwise` at the
      pinned n, repeats=3, the 5 cells, agent-sdk, SEQUENTIAL. Mechanical trace-grep clean. Watch the $
      ceiling; a runaway web cell trips the per-rollout budget guard.
- [ ] **`lift_analysis --run-id pre45`** -> the headline table + JSON. Read traces of the discordant +
      any excluded rollouts (the trust bar). Write the results into REV 4.5's results section (or a
      sibling results doc): cost ratio + CI, parity interval vs Δ (or "inconclusive"), the
      conditional-vs-ITT reliability gap, the 3-rate split, the secondary S+H−S+T lift.
- [ ] **(Optional) strong-baseline sensitivity** (pre-reg item): a higher-fetch-cap / WebFetch arm on a
      >=10-instance sample of one task — if S+H's cost/reliability edge survives, the caps weren't
      manufacturing it. (Phase 3 of the egress work already showed web reaches parity at 32MB, so this
      is largely satisfied; run only if a reviewer presses.)

## System-Wide Impact
- **Interaction graph:** `ablation.run_ablation` -> per cell `_run_cell` -> `solve_grade_write` (the
  canonical write chokepoint; UNCHANGED) -> trace rows + (NEW) a manifest. `lift_analysis` is a pure
  READER of those rows — it fires nothing, mutates nothing, touches no DB. `lift_pairwise_validate`
  reads PG + the Clerk (read-only, like `lift_roster_spotcheck`).
- **Error propagation:** a malformed/short trace row -> `lift_analysis` skips it and reports the drop
  (never crashes the report); a missing manifest -> hard error (the run-id is wrong); `cost is None`
  (no `ResultMessage` cost) -> excluded from cost stats with a reported coverage fraction; an
  all-excluded cell -> reported as "no gradeable rollouts" (not a divide-by-zero). The powered run
  inherits ablation.py's existing per-rollout budget/timeout guards + the `sandbox_infra` exclusion.
- **State lifecycle:** `lift_analysis` is idempotent + side-effect-free except writing its own
  `lift_analysis_<run_id>.json`. Re-running on the same `run_id` reproduces the report (bootstrap seed
  pinned). The manifest makes "which files belong to this run" deterministic (no stale-glob bleed).
- **API surface parity:** the analysis reads the SAME trace schema both backends write; no second path.
  ablation.py keeps ONE scoring path (`classify` + the `sandbox_infra` route), unchanged.
- **Integration scenarios (tests):** (1) synthetic traces with a known 2×2 -> McNemar + Newcombe match
  the PUBLISHED oracles; (2) a cell where S+T truncates on instances S+H solves -> conditional says
  "parity", ITT favors S+H (the reliability gap surfaces, not hidden); (3) `cost=None` on EITHER arm ->
  that instance dropped from BOTH cost vectors (index-aligned), pairwise coverage < 100% reported,
  bootstrap on the rest; (4) zero-discordance (b=c=0) -> "not applicable" + pivot, no fabricated χ²;
  (5) over-refusal read from the ANSWERABLE arm (`decision_correct==0`) — refusal twins are filtered
  before cells run (`ablation.py:188`), so they do NOT appear in a real run's traces; a separate
  hermetic test grades a synthetic refusal row via `refusal_correct` (unit-level only); (6) manifest
  round-trip: ablation writes the crash-safe manifest -> lift_analysis reads the EXACT cell set +
  asserts hash-homogeneity + paired set-equality.

## Alternative Approaches Considered
- **Add `scipy`/`statsmodels`** for the stats: REJECTED — a heavy dependency for ~6 small, stable,
  hermetically-testable functions; `numpy` (already present) + `math` suffice and keep the analysis
  self-contained and auditable (every formula visible + cited).
- **Compute stats INSIDE `ablation.py`** (extend `_print_summary`): REJECTED — couples the billable
  runner to the (iterating) analysis; the scope mandates a SEPARATE reader so analysis can be re-run /
  refined on existing traces without re-spending. ablation.py gets only the minimal manifest/run-id tag.
- **Glob `ablation_*.jsonl` by timestamp** instead of a manifest: REJECTED — fragile (stale pilot files
  bleed in; the dir already has dozens). The manifest is deterministic provenance + serves the pre-reg.
- **Straight to the powered n=40 run** (skip the smoke): REJECTED by the scope — Phase 3 showed 100%/
  100% (degenerate accuracy) and the small×web cells have never run under the gate; the ~$15 smoke
  sizes the ~$300-450 spend and may cut n (and cost) materially.
- **NHST-first (chase p<0.05)**: REJECTED — at N<=40 McNemar is power-starved (can't reach p<0.05 until
  b+c>=6; degenerate at ceiling). Estimation-first (CIs + pre-registered equivalence margin) is the
  honest posture (Card et al. 2020).

## Acceptance Criteria
### Functional
- [ ] `lift_analysis.py` computes, per (template, model-pair): exact McNemar (b,c), Newcombe paired-diff
      CI, Wilson per-arm rates, the SINGLE primary paired-bootstrap cost-ratio CI (+ median/IQR; geo-mean
      optional sensitivity only), completion rate, flip-rate, the 3-rate split, and the secondary S+H−S+T
      lift — reading ONLY a run manifest, asserting hash-homogeneity + paired set-equality.
- [ ] Cost coverage verified (Phase-1 smoke go/no-go): `total_cost_usd` populated OR the token fallback
      fires, so the primary cost endpoint has data before any Phase-2/3 spend.
- [ ] Reliability reported as the 3 panels (completion / conditional / ITT); the conditional-vs-ITT gap
      is explicit. Accuracy parity reported as the Newcombe CI vs Δ (equivalence), never a bare p.
- [ ] `ablation.py` `--run-id` + `--template a,b` + `manifest_<id>.json`; sequential; mechanical
      trace-grep run on every powered run (any hit invalidates that rollout + investigate).
- [ ] `lift_pairwise_validate.py` passes (join cross-check + cast spotcheck) BEFORE pairwise is run.

### Non-Functional
- [ ] No new runtime dependency (stdlib + numpy only). `lift_analysis` is pure/idempotent; bootstrap
      seed pinned in the manifest (reproducible).
- [ ] Billable spend GATED: Phase-2 smoke (~$15) precedes the powered run; the powered n + a hard $
      ceiling are pinned in REV 4.5 BEFORE any powered cell; opus×ours NOT run (goal #2).
- [ ] Integrity (STRUCTURAL, not a golden-digest assert): the changed files (`ablation.py`,
      `solvers.py`, `lift_analysis.py`, `manifest.py`) are in NEITHER frozen hash's file list, so they
      cannot move `grading_contract_hash`/`content_hash`; `test_hashes.py` continues to assert the split
      invariant. The pre-reg doc SHA is committed before powered cells, passed via `--prereg-sha`, and
      stamped in the manifest; lift_analysis asserts hash-homogeneity across the loaded run.

### Quality Gates
- [ ] Hermetic stat tests reproduce the research's worked examples (exact values). `ruff` clean; full
      lab suite green (Docker-/PG-gated tests skip cleanly where unavailable).
- [ ] The Phase-2 and Phase-3 reports are read against the raw traces (trust bar) before any number is
      quoted as a result.

## Risks & Mitigations
- **Degenerate accuracy (b=c=0):** EXPECTED on member_summary (Phase 3 = 100/100). Mitigation: the
  headline is cost+reliability by design; McNemar reports "not applicable", the cost-ratio CI carries
  the claim. NOT a failure — it IS the thesis (parity, cheaper).
- **δ=0.05 unachievable at n=40:** the Newcombe CI may be wider than ±0.05 -> "inconclusive", not
  parity. Mitigation: REV 4.5 sets a realistic Δ (likely 0.10) from the smoke OR reports the honest
  "underpowered for ±0.05" — flagged, not hidden (Card et al. 2020).
- **Cost CI dominated by one expensive question at small n:** the bootstrap can't manufacture
  precision. Mitigation: report median+IQR + geo-mean ratio + name the driving question(s); prefer a
  modest n bump on the cost axis over a false-precision claim.
- **Differential dropout biases complete-case accuracy:** if the weaker arm truncates more, conditional
  accuracy flatters it. Mitigation: the ITT panel (truncation=wrong) + the reported completion rate
  bound it; the gap is itself the result.
- **Stale trace files / wrong run analyzed:** the manifest + run-id tag make the file set deterministic;
  `lift_analysis` reads ONLY the manifest's `cell_files`.
- **Budget runaway on opus/sonnet×web:** the smoke sizes the envelope; ablation's per-rollout budget +
  timeout guards + the REV 4.5 $ ceiling bound it; sequential execution keeps it observable.
- **pairwise gold subtly wrong:** the join cross-check + cast spotcheck gate it; the smoke would also
  surface a gross error cheaply before the powered spend.

## Technical-review synthesis (3 reviewers, 2026-06-29) — adopted into the plan above
Python (Kieran), simplicity, and architecture reviewers ran over the plan; all `(review …)` tags above
mark a folded-in finding. Convergent HIGH: **cost-capture under subscription** (both Python+arch) — the
primary endpoint reads `ResultMessage.total_cost_usd`, which CAN be null on the OAuth/subscription path;
mitigated by a Phase-1 cost-coverage go/no-go + a token-based fallback (`usage` -> `input/output_tokens`
in `_asolve_sdk`). Tempered by DATA the reviewers lacked: the merged Phase-3 pilots reported real costs
($0.16/$0.60/$1.26) and `result_subtype == "success"` literally — so cost capture + the exclusion literal
are EMPIRICALLY confirmed in this env; the fallback is insurance. Adopted cuts (simplicity): DEFER Holm +
the "wins everywhere" secondary; ONE primary cost statistic (bootstrap CI) + median/IQR (geo-mean
optional); TRIM pairwise validation to the join cross-check. Adopted hardening: multiple published
Newcombe oracles; PAIRWISE cost exclusion (index alignment) + `mean(B)==0` guard; two-seed split
(rollout in manifest, bootstrap in analysis JSON); `_run_cell` returns its path; `run_matrix`
orchestration + crash-safe incremental Pydantic manifest; explicit `--prereg-sha`; hash-homogeneity +
paired set-equality asserts; majority-vote tie rule after rep exclusion; `analyze()` decomposed into
pure helpers; group by FULL model id; None-subtype = non-success; the refusal-arm correction (over-
refusal from the answerable arm; twins are pre-filtered); frozen-hash claim reworded to the STRUCTURAL
guarantee. Unanimous KEEPs: no-scipy hand-rolled stats, the three-panel reliability split, the
independent join recompute, estimation-first, the staged spend with 2 STOPs.

## Pre-registration alignment (what REV 4.5 pins; the existing rev-4 already pins n=40/seed=42/cells/k=3)
REV 4.5 ADDS/CONFIRMS: final n + Δ (from the smoke); the exact stat variants (above); the primary
endpoint (cost ratio at parity, S+H vs F+T, designated cell); majority-vote rep aggregation;
bootstrap B + seed; Holm = secondary-only; the AS-RUN caps (REV 4.4); the `lift_analysis` + manifest
contract; the $ ceiling. The committed doc SHA is the anchor (stamped in the manifest); any change
after a powered cell runs invalidates + requires a new pre-reg commit.

## Sources & References
### Origin
- Scope: `docs/scopes/2026-06-29-harness-lift-full-matrix-scope.md` (selective-expand). Carried
  forward: staged execution, the analysis-script deliverable, pairwise-smoke-first, pre-reg discipline.
### Internal
- Existing pre-registration: `docs/plans/2026-06-29-feat-lab-harness-lift-ablation-plan.md` (rev 4 —
  arms, n=40, seed=42, the 5 cells, k=3, exclusion rule, McNemar/3-rate/cost/p-hat-variance metrics,
  parity δ, the mechanical trace-grep).
- `lab/ablation.py` (matrix driver; `run_ablation`, `_run_cell`, `classify`, the `sandbox_infra`
  route); `lab/experiments/lift_instances.py` (`generate_lift_member_summary`/`_pairwise`,
  `LIFT_TEMPLATES`, `_pairwise_gold`); `lab/experiments/lift_roster_spotcheck.py` (the read-only
  Clerk-check pattern to mirror); `lab/harness.py` (`prepare_run`/`solve_grade_write`/`RUNS_DIR`);
  the trace schema (`policy.surface/model`, `verdict.subscores`, `cost`, `result_subtype`).
- Keystone: [[project_condorcet_experimental_design]] (REV 4.4; arms S+H/S+T/F+T; cost/reliability-at-
  parity headline; the egress gate that unblocks this).
### External (statistical methodology — for the methods section + the hermetic test oracles)
- Newcombe (1998), *Stat. in Medicine* 17:2635-2650 (paired-difference CI, method 10) + 17:857-872
  (Wilson). McNemar (1947); Edwards (1948); Fagerland, Lydersen & Laake (2013) (exact vs mid-p McNemar).
- Brown, Cai & DasGupta (2001) (use Wilson, not Wald). Dietterich (1998) (McNemar for classifier
  comparison; power). Demšar (2006) (comparing methods; multiplicity). Card et al. (2020), EMNLP
  ("With Little Power..."; small-N benchmark power — the estimation-first posture). Efron & Tibshirani
  (1993) (bootstrap; BCa). Holm (1979); Gelman & Loken (2014) (forking paths). Schuirmann (1987) /
  Lakens (2017) (equivalence / TOST).
### Related Work
- PR #51 (lift apparatus), PR #52 (Phase-1 sandbox), PR #53 (Phase-2/3 egress + re-pilot).
