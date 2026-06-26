# statehouse-intel — Platform & Environment Spec

> **Audience:** coding agents and engineers building on this platform. **Register:** declarative and imperative, not persuasive. If you want the *why* behind a choice, see the architecture report; this doc tells you *what* to build and *what rules to follow*.
>
> **Status tags:** `[BUILT]` exists today (in System 1, the `legislative-research-tool` repo) · `[PARTIAL]` partially built · `[TARGET]` spec'd, not yet built. Do not assume a `[TARGET]` component exists; build toward it.
>
> **Scope & reconciliation — read the ecosystem map first.** This spec describes the full target *environment* an agent works in, which spans **two systems plus one program**:
> - **statehouse-intel proper is System 2** — the batch **DuckDB / versioned Parquet** modeling pipeline (crosswalk → IRT → MRP → cross-pressure → reports). Currently spec; defined authoritatively in `statehouse-intel-repo-spec.md`.
> - **The harness (§4), benchmark (§5), and observability (§6) are the Lab** — a program whose substrate is **largely already built in System 1** (Postgres + pgvector, an agentic harness, and the `autoresearch/` eval scaffold).
> - The two are bridged by the **crosswalk** (`ci_leg_id`) and nothing else.
>
> For the authoritative built-vs-spec inventory and system boundaries, see `condorcet-ecosystem-map.md`. Where this doc and the map disagree, the map wins.

---

## 1. What this system is

`statehouse-intel` is a data-driven political-advocacy intelligence platform for pro-liberty state-level organizations. Its distinctive job — the thing no incumbent does — is to surface **per-member leverage**: legislators holding positions against their own districts' demonstrated preferences, grounded in district-level opinion estimates. It does this by combining a legislative data platform, an agentic harness over that platform, and an outcome-coupled benchmark that doubles as a training/eval environment.

**Pilot state:** Louisiana. Build state-agnostic; validate on LA first.

**Relationship to System 1 (the Research Tool).** A built AI-native research platform already exists `[BUILT]` — the `legislative-research-tool` repo: Python 3.12, FastAPI, **Postgres + pgvector**, async SQLAlchemy/Alembic, an MCP/agent harness, hybrid search, and the `autoresearch/` eval scaffold; ingestion for GovInfo (federal), Open States, and LegiScan. statehouse-intel (System 2) is **standalone** and batch (DuckDB/Parquet); the **only** shared dependency is the legislator-ID **crosswalk** (`ci_leg_id`). The Lab (harness/benchmark) grows from System 1's `autoresearch/` and runs against both systems via a SQL connection. Do not create coupling between the two systems beyond the crosswalk.

---

## 2. Architecture at a glance

```
┌─────────────────────────────────────────────────────────────┐
│  HARNESS (the Lab — substrate BUILT in System 1)              │
│  bounded query substrate · orchestrator-worker · advisor-tool │
│  · Skills · compaction · GEPA-optimized prompts               │
└───────────────┬─────────────────────────────┬────────────────┘
                │ reads/computes (SQL)         │ emits traces
┌───────────────▼──────────────┐   ┌──────────▼────────────────┐
│  DATA PLATFORM                │   │  BENCHMARK / REWARD ENV    │
│  System 1: Postgres [BUILT]   │   │  (the Lab)                 │
│  System 2: DuckDB/Parquet     │   │  factual · methodological  │
│  · crosswalk · ideal-pt/MRP   │   │  · judgment · retrodiction │
│  · bitemporal · registry      │◄──┤  (consumes frozen defs)    │
│  · sensitive-data root        │   └────────────────────────────┘
└───────────────────────────────┘
                │ all activity logged as training-ready traces
┌───────────────▼──────────────────────────────────────────────┐
│  OBSERVABILITY  OTel (OpenLLMetry/OpenInference) → Langfuse    │
│  (partial infra BUILT in System 1: cost_tracker, ai_analyses) │
└───────────────────────────────────────────────────────────────┘
```

---

## 3. The data platform

### 3.1 Structured core — two stores, by system
- **System 1 (federal) `[BUILT]`:** Postgres + pgvector in `legislative-research-tool` — `bills`, `bill_actions`, `bill_texts`, `people`, `sponsorships`, `vote_events`, `vote_records`, committees, etc. Already queryable; the Family 1/10 trust floor runs here first.
- **System 2 (Louisiana) `[TARGET]`:** versioned **Parquet queried via DuckDB** (per `statehouse-intel-repo-spec.md`) — the same legislative graph for LA, plus the modeling marts.

The Lab harness speaks SQL to either store, so the same task code runs against both. The legislative graph (both stores):
- **Members** — id (`ci_leg_id`), party, chamber, district, tenure, leadership role, electoral history.
- **Bills** — id, text, status, lifecycle events, policy tags.
- **Votes / roll calls** — member × vote-event × value.
- **Sponsorship edges** — bill × member × role (primary / co).
- **Committees** — committee dimension + temporal membership + roles.
- **Districts** — demographic + electoral attributes.

**Source data — consume, do not recreate:** Open States, LegiScan, GovInfo/Congress.gov, VoteView, Shor-McCarty. (Bonica DIME is optional-future, not v1 — see §3.3.) Federal ingestion is **built** in System 1; LA ingestion is System 2 spec (reuse System 1's Open States ingester).

### 3.2 Crosswalk `[TARGET]`
Legislator-ID reconciliation across sources (`ci_leg_id`; Open States, LegiScan, VoteView, Shor-McCarty, internal). Built in **System 2** with human-review checkpoints, then **published as its own versioned dataset** that System 1 imports. **The single shared dependency between the two systems.** Every cross-source join goes through it.

### 3.3 Ideal-point store `[TARGET]`
Versioned ideology estimates keyed by `(member, estimation_run)`:
- **Shor-McCarty** scores, extended via **anchored-IRT** using returning members as bridge observations (soft-centered prior on each returning member's Shor-McCarty score).
- New members lacking roll-call history are reported as **`insufficient_votes`**, not imputed — the conservative, publish-defensible stance. **Bonica DIME / CFscores are optional-future**, not v1: a clearly-labeled later enhancement, never a silent default.
- Run-id discipline is mandatory: "the score" is never ambiguous; always cite the run.

### 3.4 MRP / district-opinion store `[TARGET]`
Versioned district-level opinion estimates keyed by `(district, issue, run)`: estimate, credible interval, reliability flag. Outputs of the Stan MRP pipeline. Treat estimates as **facts about pipeline outputs**, not ground truth.

### 3.5 Bitemporal layer `[TARGET]`
Valid-time + transaction-time on all mutable legislative state. Enables **point-in-time reconstruction** ("status as of date T") and retrodiction. **Required** before any Family 9 (temporal) benchmark task or any historical-state query.

### 3.6 Definition registry `[TARGET]` — the seam between layers
Small (~10–12 entries for v1), versioned set of **frozen operational definitions**, each with an exact computable spec over named columns. It **formalizes config the statehouse-intel spec already isolates** (vote-inclusion rules, CPI weights, classification thresholds, the issue taxonomy) and adds versioning + freeze + a grading contract. It adopts System 2's cross-pressure vocabulary as canonical:
- `position_gap@vK`, `salience_w@vK`, `vulnerability@vK`, `perception_gap@vK`
- `cross_pressure_index@vK` (CPI) and `target_class@vK` ∈ {information_target, pressure_target, low_leverage, aligned}
- supporting: `issue_to_bill_mapping@vK`, `mrp_reliability_cutoff@vK`

**Two faces:** the factual layer *consumes* frozen definitions to grade computations exactly (turns Family 8 tasks from `→M` into `C-def`); the methodological layer *produces and justifies* them. **Agents must pull leverage-computation definitions from the registry by version and cite the version. Never invent a threshold, weighting, or mapping inline.** Full schema + seed: `definition-registry-schema.md`.

### 3.7 Data taxonomy (Tier 1/2/3)
- **Tier 1** — public structured data (votes, bills, sponsors).
- **Tier 2** — derived estimates (ideal points, MRP).
- **Tier 3** — **outcome-coupled traces** (agent runs paired with elicited rationale + verifiable outcome). **Tier 3 is the moat.** Capture it deliberately from day one (see §6.4).

### 3.8 Sensitive-data root `[TARGET]`
Survey/PII data lives in a **segregated root** (System 2's `data_sensitive/`) with its own access boundary. **Never join sensitive survey PII into general outputs or traces.** Aggregate-only crossing of the boundary, through defined interfaces.

---

## 4. The harness (the Lab)

> **Status:** a working multi-model harness **already exists in System 1** `[BUILT]` — `src/llm/harness.py` + adapters, `cost_tracker`, prompt versioning, `src/agents/qa_agent.py`, an MCP server (`search_bills`, `get_bill_detail`, …), and hybrid search (BM25 + pgvector + reranker). The items below are the **target shape the Lab evolves it toward** — treat them as `[TARGET]` refinements of a `[BUILT]` substrate, not greenfield.

Design principle: **structured operators for the common case; full programmatic power only where a query genuinely needs semantic map-reduce.** (Deliberate — unrestricted "let the model write arbitrary control flow over everything" is rejected for reliability; see architecture report, RLM/LCM discussion.)

### 4.1 Bounded query substrate
The agent operates over the data platform via a **constrained operator set**:
- **SQL** over the structured core (Postgres in System 1, DuckDB in System 2) — the default for anything relational/computational.
- **Semantic map-reduce** over text corpora (bill text, transcripts, statements) — partition + per-chunk LM calls + aggregate — used **only** for genuinely semantic tasks where SQL cannot help (e.g., "classify every bill by frame").
- **Advisor-as-tool** (§4.3) for hard sub-tasks.
- **Skills** (§4.4) as the durable domain-knowledge layer.

Prefer SQL. Reach for semantic map-reduce only when the task is irreducibly semantic. Do not wrap routine queries in recursive/programmatic scaffolds — it adds latency and failure surface for no gain.

### 4.2 Orchestrator-worker
For breadth-first / parallelizable research tasks: a lead agent decomposes and delegates to parallel workers with separate contexts; workers return condensed findings; lead synthesizes. Use for tasks that exceed one context or fan out across many sources. **Do not** use multi-agent fan-out for simple single-hop queries (token cost ≈ 15× chat).

### 4.3 Frontier-advisor-as-callable-tool
An open-weight worker model runs the bulk of reasoning; a frontier model (e.g., Claude Opus) is exposed as a **callable advisor tool** the worker invokes **sparingly** on hard sub-tasks. Tunable cost/quality knob. (System 1's Codex adapters are a partial precedent for multi-model routing.)

### 4.4 Skills
`SKILL.md`-format domain-knowledge files (the durable, hand-built expertise layer). Portable, versioned. Pattern reference: PolicyEngine's open skills library. These are the cheap, high-leverage layer — invest here before model training.

### 4.5 Compaction
For long matters that exceed context: periodic natural-language memo compaction now; KV-cache compaction later. Match training shape to inference (per-window) if/when the worker is post-trained.

### 4.6 Prompt/scaffold optimization
GEPA/DSPy over logged traces to evolve prompts and scaffolds against the benchmark reward. No weight training required. Highest-ROI harness improvement; do this before any fine-tuning.

---

## 5. The benchmark / reward environment (the Lab)

Doubles as the eval suite and the RL/training environment. Three layers by checkability:

### 5.1 Factual / computational layer `[TARGET — scaffold BUILT in System 1]` — build first
The eval scaffold already exists as System 1's `autoresearch/` (frozen `prepare.py` harness + iterated solver + auto-logged experiments); the factual layer **generalizes it** from bill-outcome prediction to graded agent tasks. ~10 families, ~100 task templates, **all code-graded**, instances auto-generated from the database. Cleanliness tiers: `C` (clean), `C-def` (clean given a frozen registry definition), `→M` (kick to methodological). See the task-suite spec. **Borrow the grading methodology** (do not reinvent): BEAVER (analytical-query difficulty tiers), EHRSQL/BiomedSQL (answerability flags), TrustSQL (penalty scoring), TriageSQL (refusal classification).

### 5.2 Methodological layer `[TARGET]`
Expert-written rubrics, LLM-judge graded, all-pass metric (Harvey LAB pattern). Grades *execution of method*, not prediction of the future. Built with domain/academic partners. Consumes the definition registry (this is where definitions get justified).

### 5.3 Judgment layer `[TARGET — deprioritized]`
Genuinely contested ("strongest argument," "right strategic call"). Grade as **preference** (pairwise expert comparison, tracked inter-rater agreement), kept small and ring-fenced. Do not fake determinism here. Expected to improve largely as a byproduct of fixing the lower layers.

### 5.4 Outcome coupling & retrodiction `[TARGET]`
Public legislative outcomes are **validation data, not per-task reward** (too confounded, too slow). Retrodiction over the historical record is a free, large, semi-deterministic task source: reconstruct state as of date T, score predictions against what actually happened. Requires the bitemporal layer (§3.5).

---

## 6. Observability & trace capture (the Lab)

### 6.1 Instrumentation `[TARGET]`
Instrument once with **OpenTelemetry** (OpenLLMetry / OpenInference). Backend-agnostic by design.

### 6.2 Backend `[TARGET]`
**Self-hosted Langfuse** (MIT, data-sovereign, OTel-native, prompt + eval). Self-hosting is mandatory given per-org enclaves and the sensitive-data root — no shipping traces to vendor SaaS.

### 6.3 Trace schema `[TARGET — partial infra BUILT in System 1]` — design once, upstream of everything
Partial provenance/cost infra already exists in System 1 (`cost_tracker`, the append-only prompt-versioned `ai_analyses` table, the `autoresearch/` experiment logs); the trace schema **extends** these. Every agent run logged as a **training-ready trace**: token-level where available, paired with a **verifiable outcome signal** and an **elicited rationale**. This is the Tier 3 moat data. The schema must serve both harness improvement (GEPA) and model training (SFT/distillation/RFT) — design it before deepening the harness.

### 6.4 Capture discipline
Log everything as training-ready from day one. A run not captured in the trace schema is moat data permanently lost.

---

## 7. Cross-cutting constraints (apply everywhere)

- **Privilege / federation / enclaves** `[TARGET]` — per-org data isolation. The eventual specialist model is served as **per-org LoRA adapters on a shared base**, not N full models. Governance for what data may be pooled across orgs vs. siloed must be settled before any cross-org pooling.
- **Point-in-time freeze** — historical reconstruction uses bitemporal queries; never current state. Definitions and harness versions are frozen and versioned alongside data.
- **Definition versioning** — every leverage computation cites a registry version.
- **Data sovereignty** — self-hostable, permissively-licensed dependencies only for anything in the multi-tenant path (MIT/Apache; avoid Elastic-License/SSPL components).
- **Provenance** — every fact carries a source record ID.

---

## 8. Build priority order

> Superseded for the **cross-system** view by the two-track path in `condorcet-ecosystem-map.md` §5 (federal trust floor now; LA in parallel). The ordering below holds *within* the benchmark/Lab program.

1. **Trace schema + OTel + self-hosted Langfuse** (§6) — the decision that compounds; design before deepening the harness.
2. **Factual layer: Family 10 (integrity/provenance) + Family 1 (roll-call)** against System 1's federal Postgres — the trust floor. Cheapest, highest brand-protective value, runnable now.
3. **Engine-agnostic task harness** (generalize `autoresearch/`; SQL connection in config) so the same tasks run against LA.
4. **Factual families 2–7** (sponsorship, status, committee, bio, ideal-point, district).
5. **Definition registry** — before any Family 8 leverage task.
6. **Factual family 8 (leverage joins)** + **family 9 (retrodiction)** once the LA models and bitemporal exist.
7. **GEPA/DSPy prompt optimization** over logged traces.
8. **Methodological layer** with expert partners.
9. **Model training** (SFT → distillation → RFT) — only after the benchmark exists at scale and the cheap rungs have plateaued.

---

## 9. Guardrails (hard rules for agents)

- **Never fabricate a vote, sponsor, member, or fact.** Every fact returns with a source record ID, or it is not returned.
- **"Not in the data" is a valid and required answer.** Do not guess to appear helpful. Refusal is graded.
- **Pull leverage definitions from the frozen registry, cite the version.** Never invent a threshold, weighting, or issue→bill mapping inline.
- **Respect the sensitive-data root boundary.** Never join survey PII into general outputs or traces; aggregate-only crossings through defined interfaces.
- **Point-in-time discipline.** For any historical-state question, use bitemporal queries; never substitute current state.
- **Prefer SQL.** Use semantic map-reduce only for irreducibly semantic tasks; never wrap routine queries in recursive scaffolds.
- **Crosswalk is the only cross-system coupling.** Do not introduce new dependencies between System 1 and System 2 beyond the crosswalk.
- **Emit training-ready traces** for every run (outcome + rationale + provenance).
- **Only self-hostable, permissively-licensed components** in the multi-tenant path.

---

## 10. Glossary

- **System 1 / System 2 / Lab** — the built Research Tool (`legislative-research-tool`, Postgres) / the spec'd statehouse-intel batch pipeline (DuckDB, LA) / the benchmark+harness+training program that runs over both. See `condorcet-ecosystem-map.md`.
- **Crosswalk** — legislator-ID reconciliation (`ci_leg_id`); the one shared dependency between System 1 and System 2.
- **Ideal point** — a legislator's estimated ideological position (Shor-McCarty; DW-NOMINATE family).
- **Anchored-IRT** — item-response model extended using returning members as bridge observations to place new members on a common scale.
- **DIME / CFscore** (Bonica) — ideology estimates from campaign-finance data; **optional-future** enhancement for members lacking roll-call history (v1 reports `insufficient_votes` instead).
- **MRP** — multilevel regression with poststratification; produces district-level opinion estimates. Cheaper than direct polling, not more accurate; feasible where direct polling isn't.
- **Cross-pressure index (CPI) / target_class** — the frozen, versioned composite measuring tension between a member's position and their district's estimated preference, and its derived classification (information_target / pressure_target / low_leverage / aligned). Lives in the definition registry.
- **position_gap / salience_w / vulnerability / perception_gap** — the CPI inputs (per System 2 §10). `perception_gap` is the Broockman-Skovron misperception term (legislator's stated belief − MRP estimate).
- **Broockman-Skovron decomposition** — three-way split: legislator's position, district's opinion, legislator's *belief* about district opinion. The empirical anchor for the leverage thesis.
- **Retrodiction** — reconstructing historical state as of a past date and scoring predictions against recorded outcomes; a free labeled-task source.
- **Bitemporal / point-in-time** — storing valid-time + transaction-time so any past state can be reconstructed exactly.
- **C / C-def / →M** — task cleanliness: clean / clean-given-frozen-definition / kick-to-methodological.
- **Definition registry** — versioned set of frozen operational definitions; the seam between factual and methodological layers.
- **Tier 1/2/3** — public structured data / derived estimates / outcome-coupled traces (Tier 3 = moat).
- **Advisor-as-tool** — frontier model exposed as a sparsely-called tool to an open-weight worker.
- **Orchestrator-worker** — lead agent decomposes and delegates to parallel workers with separate contexts.
- **RLVR** — reinforcement learning with verifiable rewards.
- **LoRA enclave** — per-org fine-tuned adapter on a shared base model.
