# Condorcet / statehouse-intel — Ecosystem Map & Path

> **What this is.** The single front door. It situates every piece of work — the existing repo, the statehouse-intel spec, and everything we designed this session — into one coherent picture, says honestly what is *built* vs *spec*, locks the architecture decisions, and lays out the path from the current starting point to the designed endpoint. Read this first; everything else hangs off it.
>
> **Confidence note.** "Built" below means *present and scaffolded in the `legislative-research-tool` repo* (verified by reading the code), not *verified working end-to-end at runtime*. Treat runtime/completeness as "to confirm on first run."

---

## 1. The shape in one picture

```
        ┌───────────────────────────────────────────────────────────────┐
        │                        THE LAB  (program)                      │
        │   benchmark (Family 1..10) · definition registry · trace/      │
        │   training flywheel.  Grows from autoresearch/. Speaks SQL to   │
        │   whichever system holds the data.                             │
        └───────────────┬───────────────────────────────┬───────────────┘
                        │ runs against                   │ runs against
        ┌───────────────▼──────────────┐   ┌─────────────▼───────────────┐
        │  SYSTEM 1: Research Tool      │   │  SYSTEM 2: statehouse-intel  │
        │  [BUILT]                      │   │  [SPEC — draft for build]    │
        │  Postgres + pgvector, FastAPI │   │  DuckDB / Parquet, Stan      │
        │  MCP, multi-model harness,    │   │  crosswalk → IRT → network → │
        │  hybrid search, agents,       │   │  MRP → cross-pressure →      │
        │  bill-outcome + autoresearch  │   │  reports                     │
        │  Federal-heavy + OpenStates   │   │  Louisiana                   │
        └───────────────┬──────────────┘   └─────────────┬───────────────┘
                        │                                 │
                        └────────── CROSSWALK ────────────┘
                            ci_leg_id — the one shared artifact
```

Two systems, one bridge, one program. They are deliberately different shapes because they do different jobs: System 1 is an **online agentic research/QA/analysis service**; System 2 is a **reproducible batch modeling pipeline**. The Lab evaluates and trains over both.

---

## 2. The bodies of work

### System 1 — the Research Tool (`legislative-research-tool`) · BUILT
AI-native legislative research platform. **This is the harness substrate and the starting point.**
- **Stack:** Python 3.12, FastAPI, **Postgres + pgvector**, async SQLAlchemy/asyncpg, Alembic. Anthropic + OpenAI + Codex adapters; MCP; Claude Agent SDK.
- **Data (Postgres, ~35 tables):** `bills`, `bill_actions`, `bill_texts`, `bill_embeddings`, `people`, `organizations`, `sponsorships`, `vote_events`, `vote_records`, `committee_hearings`, `crs_reports`, `ai_analyses` (append-only, prompt-versioned), `ingestion_runs`, `jurisdictions`, `sessions`, plus a policy-drafting workspace.
- **Ingestion:** GovInfo (federal Congress 110–118), congress_legislators, CRS, Federal Register, committee hearings, **LegiScan, Open States**.
- **Harness:** `src/llm/harness.py` + adapters, `cost_tracker`, prompt versioning; `src/agents/qa_agent.py`; `src/mcp/server.py` (search_bills, get_bill_detail, …); `src/search/` (BM25 + pgvector + reranker).
- **Eval embryo:** `autoresearch/` — frozen `prepare.py` (Postgres connection, temporal train/val/test splits, standardized scoring, auto-logged experiments), agent-iterated `train.py`, `promote.py`, baselines. **This is the benchmark skeleton.**
- **Scope:** federal-heavy; state via Open States/LegiScan. No crosswalk, no ideal-point/MRP/cross-pressure work (confirmed absent).

### System 2 — statehouse-intel · SPEC (draft for build)
The quantitative representation/advocacy-targeting pipeline. **This is the differentiator, and it is unbuilt.**
- **Stack:** Python 3.12, uv, polars, **DuckDB / versioned Parquet**, pandera, **Stan (cmdstanpy)** for IRT/MRP, networkx, jinja2/weasyprint. Batch; no API server in v1.
- **Modules:** `ingest/` (openstates, shor_mccarty, la_ethics, ftm, census_acs, elections) → `crosswalk/` (`ci_leg_id`) → `marts/` (legislator_core, rollcall_matrix, sponsorship_edges, money_summary, district_profile, legislator_profile) → `models/` (irt, network, mrp, **crosspressure**) → `survey/` (sensitive root) → `outputs/` (chamber report, issue brief, cross-pressure target memo).
- **Cross-pressure output (§10 of its spec):** per (legislator, issue): `position_gap`, `salience_w`, `vulnerability`, `perception_gap`, `CPI`, and `target_class` ∈ {information_target, pressure_target, low_leverage, aligned}. **This vocabulary is canonical** — the registry and all leverage work adopt it.
- **Scope:** Louisiana pilot. Ships a chamber report on pure public data before any survey dollar.

### Bridge — the crosswalk · the one coupling
`ci_leg_id` / `ci_dist_id` / `ci_bill_id`. Built in System 2, published as its own versioned dataset, imported by System 1. Nothing else couples the two systems.

### Program — the Lab · DOCS + embryo
The benchmark + definition registry + trace/training flywheel designed this session. **Grows from `autoresearch/`**, generalized from bill-outcome prediction to the factual/methodological/judgment task families. Speaks SQL to a connection, so it runs against System 1 (Postgres, federal) and System 2 (DuckDB, LA) interchangeably.

---

## 3. Built vs spec — honest inventory

| Capability | Where | Status |
|---|---|---|
| Federal bills/votes/people/sponsors in queryable DB | System 1 | **Built** |
| Ingestion: GovInfo, Open States, LegiScan | System 1 | **Built** |
| Agentic harness (multi-model, MCP, cost tracking, search) | System 1 | **Built** |
| Eval scaffold (frozen harness / iterated solver / logged experiments) | System 1 `autoresearch/` | **Built (embryo)** |
| Bill-outcome prediction (the deferred "feature feed") | System 1 | **Built (embryo; see §6 caveat)** |
| Crosswalk (`ci_leg_id`) | System 2 | **Spec** |
| LA ingestion (ethics, FTM, ACS, elections, Shor-McCarty) | System 2 | **Spec** |
| IRT ideal points (anchored) | System 2 | **Spec** |
| MRP district opinion | System 2 | **Spec** |
| Cross-pressure index + target_class | System 2 | **Spec** |
| Survey module (citizen + legislator, sensitive root) | System 2 | **Spec** |
| Factual benchmark (Family 1..10) | Lab | **Design + reusable scaffold** |
| Definition registry | Lab | **Design** |
| Training-ready trace schema | Lab | **Design (partial infra in System 1: cost_tracker, ai_analyses)** |

---

## 4. Architecture decisions — locked

Recorded here in brief; expand into `docs/adr/` when convenient.

1. **Two stores, by system.** Postgres + pgvector for System 1 (online, agentic). DuckDB + versioned Parquet for System 2 (batch, reproducible, publishable). Not a conflict — a deliberate split. *(Corrects this session's earlier "Postgres structured core" for statehouse-intel, which was wrong.)*
2. **The Lab harness speaks SQL to a connection.** Family 1..10 task code is engine-agnostic, so "run the benchmark on LA" is a connection swap, not a rewrite. This is what makes "do the same on LA" cheap.
3. **The Lab grows from `autoresearch/`** inside the Research Tool repo (reuse the harness, the eval scaffold, and the federal data already there). statehouse-intel stays its own repo. Crosswalk bridges them. *(Sibling-repo isolation remains acceptable but would rebuild scaffolding you already have.)*
4. **DIME is optional-future, not v1.** Keep statehouse-intel's conservative IRT stance: anchor via returning members on Shor-McCarty; report `insufficient_votes` rather than impute. DIME/CFscores only as a clearly-labeled later enhancement.
5. **The definition registry formalizes config the spec already isolates** (vote-inclusion rules, CPI weights, thresholds, taxonomy) and adds versioning + freeze + grading contract + dependency DAG. It adopts System 2's CPI vocabulary and `target_class` as canonical, retiring this session's parallel coinages (divergence/leverage_score → position_gap/CPI/target_class; belief_gap → perception_gap).
6. **Crosswalk is the only coupling.** Per System 2's principle: external systems are dependencies, not couplings.

---

## 5. The path — two tracks, converge, then diverge

Two tracks run partly in parallel. They meet at "Family 1+10 on LA," then split upward where the differentiator lives.

**Track A — the Lab on federal data (runnable now).** Reuses System 1's harness + `autoresearch/` scaffold + already-ingested federal data.

**Track B — statehouse-intel / Louisiana (parallel, longer lead).** Builds System 2 from its spec; the survey/MRP portion is dollar- and calendar-gated.

### Sequence

1. **Generalize `autoresearch/` into an agent-eval harness** and write **Family 1 (roll-call retrieval/aggregation)** and **Family 10 (integrity / provenance / refusal)** generators + code-graders against the existing federal Postgres (`vote_events`, `vote_records`, `people`, `sponsorships`, `bills`). Run the existing `qa_agent`/MCP harness as the agent-under-test. *Reuses: harness, eval scaffold, federal data. Runnable this week.*
2. **Formalize the training-ready trace schema** (extend `cost_tracker` + `ai_analyses` + the experiments log) so step-1 runs are captured as Tier-3 data from the first run; stand up the **empty-but-governed definition registry**. *The two "design once" things.*
3. **Ingest LA + build the crosswalk** (`ci_leg_id`) — System 2 spec steps 1–3; reuse System 1's Open States ingester. *The bridge.*
4. **Run Family 1+10 against LA** — connection swap (decision #2). *Trust floor on both jurisdictions.*
5. **Build statehouse-intel models** (IRT → network → MRP → cross-pressure) and **ship the public-data chamber report** — System 2 spec steps 4–10. *The differentiator's substrate.*
6. **Seed the registry from the cross-pressure config**, get the contested parameters **blessed by a political scientist**, and build **Family 8 (leverage)** as C-def tasks. *The moat layer; first hard methodological gate.*
7. **The endpoint proper** — retrodiction, GEPA harness optimization, the methodological layer, and eventually the specialist model.

### Long-lead threads to start at step 1 (not when they're "due")
Expert/relationship pipeline (the political scientist who blesses the registry; Erspamer/Pelican) · the LA survey (dollars + calendar) · bitemporal design in System 2 · trace discipline. These gate steps 5–6 and cannot be compressed late.

---

## 6. Where the differentiator and the moat actually are

- **Federal Family 1+10 proves the machinery and the trust floor — not the product.** Leverage needs MRP district opinion, which is LA/System-2 and gated on a real poll. Don't let a fast federal win imply the hard part is done; it's all on Track B.
- **The moat is not the harness or a trained model** (both copyable/depreciating). It's the **outcome-coupled benchmark + the LA representation data + the relationships** — the parts no one else is positioned to build.
- **Integrity caveat, live in your own repo:** `autoresearch/train.py` reports ~0.99 AUROC on bill-outcome prediction — almost certainly leakage from post-outcome features (`action_count`, `days_active`, `last_action_date` accrue *after* committee passage). This is exactly what Family 10 (point-in-time integrity) exists to catch, and it's a concrete argument for building the integrity layer first. Worth a fix in `prepare.py` to exclude post-decision features before that number is trusted or shown to anyone.

---

## 7. Document index — the front door

| Artifact | Role | Status |
|---|---|---|
| **this file** | ecosystem map + path | current |
| `statehouse-intel-repo-spec.md` | System 2 build spec (canonical for the LA pipeline) | authoritative |
| `legislative-research-tool` repo | System 1 (built); its own `CLAUDE.md` is authoritative for System-1 conventions | authoritative |
| `statehouse-intel-platform-spec.md` (session) | agent-facing platform spec | **needs correction:** storage-by-system; re-tag harness/benchmark to "built in System 1" |
| `definition-registry-schema.md` (session) | registry schema + seed | **needs rework:** adopt CPI vocabulary + `target_class`; frame as formalizing System 2 config |
| `CLAUDE.md` (session) | agent brief / guardrails | **reconcile** with System 1's existing `CLAUDE.md`; keep the hard rules |
| `lab-factual-layer-task-suite.md` | Family 1..10 task design | current; transplant grading (BEAVER/EHRSQL/TrustSQL/TriageSQL) |
| `lab-prior-art-and-landscape.md` | prior art + borrow/build + moat | current |
| `statehouse-intel-roadmap.md` (session) | phased roadmap | **superseded by §5 here** (two-track path) for the cross-system view |

---

## 8. Handoff to Claude Code / Codex (stub — next artifact)

When you move to Claude Code and Codex, the next artifact is a **repo-scoped task pack** built from §5. Outline:

- **Repo & branch:** `legislative-research-tool`; Track A work lands here (Lab grows from `autoresearch/`).
- **Working agreement:** which files are *fixed* (the frozen task harness, mirroring `prepare.py`'s "do not modify" rule) vs *iterated*; commit conventions (already in the repo's `CLAUDE.md`); how traces are logged; the hard rules from the session `CLAUDE.md` (never fabricate; "not in the data" is valid; point-in-time discipline).
- **First epics (Track A, steps 1–2):**
  1. Generalize `autoresearch/prepare.py` into an engine-agnostic **task harness** (SQL connection in config; auto-generate + code-grade; auto-log).
  2. **Family 1** generators/graders over `vote_events`/`vote_records`/`people`/`sponsorships`/`bills` (federal).
  3. **Family 10** integrity/refusal generators (including a "not in the data" set and a point-in-time set; fix the `autoresearch` post-outcome-feature leakage as the first integrity exemplar).
  4. **Trace schema** v0 (extend `cost_tracker` + `ai_analyses`); **registry** scaffold (empty, governed).
- **Acceptance criteria per task**, written so an agent can self-check (gold computed by the harness; citation-of-source required; refusal graded).
- **Codex vs Claude Code split:** suggest Claude Code for the agent-harness/trace work (it touches the existing agentic code it understands well) and Codex for the self-contained generator/grader functions and SQL — but this is a preference, not a rule.

*Say the word and I'll write this task pack as its own file, sized for the two agents.*
