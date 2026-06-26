# CLAUDE.md — Condorcet (cross-cutting brief)

> Always-loaded brief for agents working on **any** Condorcet repo. Read this first, every task. Obey **Hard rules** without exception.
>
> **Placement.** This is the *cross-cutting* layer. Each repo keeps its **own** `CLAUDE.md` for repo-specific conventions and commands — System 1 (`legislative-research-tool`) already has one; System 2 (`statehouse-intel`) will. Reference this brief *from* those files; do not overwrite a repo's existing `CLAUDE.md` with it. Where this brief and a repo's `CLAUDE.md` disagree on a convention, the repo's file wins for that repo; the **Hard rules** below always hold.

---

## What this is

Condorcet builds advocacy intelligence for pro-liberty organizations. The distinctive job — the thing no competitor does — is **per-member leverage**: surfacing legislators who hold positions *against their own districts' demonstrated preferences*, using district-level opinion estimates. When you make a local decision, optimize for *trustworthy, computable, outcome-coupled* intelligence — not fluent-sounding output.

Pilot state for the leverage work: **Louisiana**. Build state-agnostic.

---

## Read first (front door + deeper docs)

- `condorcet-ecosystem-map.md` — **the front door.** System 1 / System 2 / crosswalk / Lab, what's built vs spec, the two-track path. Read this before assuming what exists.
- `statehouse-intel-repo-spec.md` — System 2 build spec (the LA batch pipeline). Canonical for that system.
- `statehouse-intel-platform-spec.md` — agent-facing environment spec (data platform, harness, benchmark, guardrails).
- `lab-factual-layer-task-suite.md` — the benchmark's factual layer (~100 task templates, code-graded).
- `definition-registry-schema.md` — the frozen operational definitions (CPI vocabulary) behind every leverage computation.
- `lab-prior-art-and-landscape.md` — what to borrow vs. build.
- System 1's own `CLAUDE.md` (in `legislative-research-tool`) — authoritative for System-1 conventions/commands.

If a task touches leverage/cross-pressure → registry doc. The benchmark → task-suite doc. Data/harness structure → platform spec. System boundaries / what's built → ecosystem map.

---

## Mental model (hold these five)

1. **Two systems + a bridge + a program.** **System 1** (`legislative-research-tool`, BUILT) — Postgres/pgvector, agentic, federal-heavy research/QA. **System 2** (`statehouse-intel`, SPEC) — DuckDB/Parquet batch modeling (IRT/MRP/cross-pressure), LA. **Crosswalk** (`ci_leg_id`) bridges them. **The Lab** — benchmark + registry + trace/training flywheel — runs over both and grows from System 1's `autoresearch/`.
2. **Storage is by system.** Postgres (System 1) and DuckDB/Parquet (System 2). The Lab harness speaks SQL to either; the same task code runs against both.
3. **Cleanliness tiers.** Benchmark tasks are `C` (clean), `C-def` (clean given a frozen registry definition), or `→M` (kick to the methodological layer). Never fake `C`/`C-def` over a contestable choice.
4. **The registry is the seam.** Every contestable definition (CPI weights, classification thresholds, mappings) is frozen and versioned. Computations *consume* frozen definitions by version; experts *produce/justify* them.
5. **Tier 3 is the moat.** Outcome-coupled traces (run + rationale + verifiable outcome) are the durable asset. Capture them on every run; a run not logged in the trace schema is moat data lost forever.

---

## Hard rules (non-negotiable)

- **Never fabricate** a vote, sponsor, member, bill, score, or estimate. Every fact returns with a source record ID, or it is not returned.
- **"Not in the data" is a valid and required answer.** Do not guess to seem helpful. Refusal is graded.
- **Leverage definitions come from the frozen registry, cited by `id@version`.** Never inline a threshold, weight, or issue→bill mapping. Computing the right number against the wrong definition version is a failure.
- **Respect the sensitive-data root.** Never join survey/PII into general outputs or traces. Aggregate-only crossings, through defined interfaces.
- **Point-in-time discipline.** Any historical-state question uses bitemporal queries — never substitute current state. (Watch for post-outcome feature leakage; it is the canonical integrity failure.)
- **SQL-first.** Use the structured core via SQL for anything relational/computational. Reach for semantic map-reduce only for irreducibly semantic tasks. Never wrap routine queries in recursive scaffolds.
- **Crosswalk is the only cross-system coupling.** Do not add new dependencies between System 1 and System 2 beyond the crosswalk.
- **Trace everything** as training-ready (outcome + rationale + provenance).
- **Multi-tenant path is self-hostable + permissively licensed only** (MIT/Apache; no Elastic-License/SSPL components).
- **Don't fabricate a frozen definition.** If a needed definition isn't in the registry or isn't frozen, stop and surface it — do not invent a value to proceed.

---

## Conventions

- **Stack, by system.** System 1: Python 3.12, FastAPI, **Postgres + pgvector**, async SQLAlchemy/Alembic, MCP, TypeScript frontend. System 2: Python 3.12, uv, polars, **DuckDB / Parquet**, pandera, Stan (cmdstanpy), networkx. Estimates (ideal-point, MRP) are **run-versioned**; always pin and cite the run.
- **Status tags:** `[BUILT]` (in System 1) / `[PARTIAL]` / `[TARGET]`. Do not assume a `[TARGET]` thing exists; check the ecosystem map before depending on it.
- **IDs:** `ci_leg_id` / `ci_dist_id` / `ci_bill_id`. Nothing joins on names downstream of the crosswalk.
- **Docs:** technical docs in Markdown; agent-facing docs declarative, human strategy docs separate.
- **Borrow before building:** consume data sources (Open States, LegiScan, GovInfo/VoteView, Shor-McCarty); transplant grading methodology (BEAVER tiers, EHRSQL answerability, TrustSQL penalty scoring, TriageSQL refusal). (Bonica DIME is optional-future, not a default.)
- **Skills vs. this file:** this brief orients agents building the systems. The runtime **Skills** (`SKILL.md` files, plural) are the harness's domain-knowledge layer — a different artifact set.

---

## Build path (for unscoped tasks)

Cross-system order is the two-track path in `condorcet-ecosystem-map.md` §5. In short:

1. **Generalize System 1's `autoresearch/`** into an engine-agnostic agent-eval harness; build **Family 1 (roll-call) + Family 10 (integrity/refusal)** against the **existing federal Postgres**. Runnable now.
2. **Trace schema** (extend `cost_tracker` / `ai_analyses`) + **registry scaffold**. The two "design once" things.
3. **Ingest LA + build the crosswalk** (System 2). Then run Family 1+10 against LA (connection swap).
4. **statehouse-intel models** (IRT → MRP → cross-pressure) + ship the public-data chamber report.
5. **Seed registry from the cross-pressure config, get it blessed, build Family 8 (leverage).** First hard methodological gate.
6. Retrodiction → GEPA → methodological layer → model training (**last**, gated on the benchmark at scale).

Start the long-lead human threads (expert/relationship pipeline, the LA poll) at step 1 — they gate steps 4–5 and cannot be compressed late.

---

## Commands

Per repo (see each repo's own `CLAUDE.md`):
- **System 1** (`legislative-research-tool`): `uvicorn src.api.app:app --reload` · `pytest` · `ruff check` · `alembic upgrade head` · `python -m src.cli` · `autoresearch/`: `cd autoresearch && python train.py`.
- **System 2** (`statehouse-intel`): uv-managed; thin `typer`/`make` CLI per its spec (`ingest_all`, `build_crosswalk`, `build_marts`, `fit_irt`, `fit_mrp`, `build_crosspressure`, `render_report`).

---

## Vocabulary (must-knows)

- **System 1 / System 2 / Lab** — built Research Tool / spec'd LA pipeline / the benchmark+harness+training program over both.
- **Crosswalk** — legislator-ID reconciliation (`ci_leg_id`); the one cross-system dependency.
- **Ideal point** — estimated legislator ideology (Shor-McCarty; anchored-IRT). New members without roll-call history → `insufficient_votes`, not imputed (DIME optional-future). Run-versioned.
- **MRP** — district-level opinion estimates; cheaper than direct polling, not more accurate. Run-versioned.
- **CPI / target_class** — the cross-pressure composite and its classification {information_target, pressure_target, low_leverage, aligned}; the headline output. Inputs: `position_gap`, `salience_w`, `vulnerability`, `perception_gap`. Defined in the registry.
- **Broockman-Skovron decomposition** — member position vs. district opinion vs. member's *belief* about district opinion (`perception_gap`). The empirical anchor.
- **Retrodiction** — reconstruct past state, score predictions against recorded outcomes; a free labeled-task source.
- **C / C-def / →M** — task cleanliness tiers (see Mental model #3).
- **Tier 1/2/3** — public structured data / derived estimates / outcome-coupled traces (Tier 3 = moat).

---

## When unsure

- Missing or unfrozen definition → **stop and surface it.** Never invent a value to proceed.
- Contestable choice masquerading as a fact (a threshold, a mapping) → it belongs in the registry / methodological layer, not inline. Flag it.
- Data not present → answer "not in the data," with what *is* known.
- Conflict → this file's **Hard rules** win; the **ecosystem map** wins on system boundaries / built-vs-spec; a repo's own `CLAUDE.md` wins on that repo's conventions; otherwise the platform spec is authoritative. If still unclear, ask rather than guess.
