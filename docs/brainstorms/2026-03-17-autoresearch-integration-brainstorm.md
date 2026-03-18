# Brainstorm: Autoresearch Integration for Bill Outcome Prediction

**Date:** 2026-03-17
**Status:** Draft
**Related:** `AI_Legislative_Research_Tool_Roadmap.md` (Phase 3 Item 4), `docs/plans/2026-03-02-feat-phase4c-historical-analysis-plan.md`

## What We're Building

An autonomous experimentation module (`autoresearch/`) that uses the Karpathy autoresearch pattern to develop a bill outcome prediction model. An AI coding agent iterates on a single `train.py` file against a fixed evaluation harness (`prepare.py`), optimizing AUROC on committee-passage prediction using historical legislative data.

The prediction engine will surface probabilities like "this bill has a 34% chance of clearing committee" as a user-facing feature for policy researchers.

## Why Now (4C Synergy)

Phase 4C (historical analysis / trends API) and autoresearch share the same critical prerequisite: **historical federal data with resolved outcomes**. Neither the trends endpoints nor the prediction model work without multi-session backfill data. Building the shared data foundation once serves both workstreams and avoids duplicate ingestion engineering.

## Why This Approach

**Approach chosen: Thin prerequisite layer, then fork**

Build only the shared prerequisites (backfill infrastructure + `introduced_date` migration), then let autoresearch and Phase 4B/4C diverge as independent parallel workstreams.

**Why not a unified workstream?** Coupling autoresearch (an R&D sandbox) to Phase 4 platform release cadence would slow both down. The autoresearch module is intentionally self-contained — it reads from Postgres but operates independently.

**Why not autoresearch-first?** 4C is already in flight and benefits equally from the backfill. Doing shared work first is more efficient than letting one workstream drive data requirements the other also needs.

## Key Decisions

1. **Backfill scope: Federal only (Congress 110-118, ~2007-2024)**
   - Covers the autoresearch temporal split (train 2010-2022, validate 2023, test 2024)
   - ~10K bills per Congress, manageable volume
   - State data expansion deferred until federal experiments prove the loop works

2. **Add `introduced_date` column to bills table**
   - New migration, backfilled from `bill_actions` (first action with `introduction` classification)
   - Benefits both 4C trend bucketing (currently using imprecise `created_at`) and autoresearch temporal splits
   - More accurate than `session_start` proxy

3. **Autoresearch uses raw psycopg2, not the ORM**
   - `prepare.py` connects directly to Postgres with `psycopg2`
   - Does not import from `src/models/` — clean sandbox boundary
   - The agent only sees `train.py`; the harness SQL in `prepare.py` is human-maintained

4. **Production promotion path: new `src/prediction/` module**
   - When a model meets quality bar, `promote.py` bridges to a new `src/prediction/` module
   - Prediction is tabular ML, not LLM-based — doesn't belong in `src/llm/` harness
   - New API endpoint `GET /bills/{id}/prediction` served from this module

5. **Sequencing: shared prereqs first, then parallel**
   - Step 1: `introduced_date` migration (no dependencies)
   - Step 2: Extend GovInfo ingester to support congress range parameter
   - Step 3: Run federal historical backfill (Congress 110-118)
   - Step 4: Fork — resume 4B/4C + set up autoresearch directory
   - Autoresearch experiments run in parallel with ongoing platform work

6. **Agent execution: manual first, automate later**
   - Validate harness manually with a few experiments
   - Switch to autonomous overnight runs once setup is trusted
   - Expect 0.65-0.70 AUROC from baseline, targeting 0.80+ with feature engineering

## Shared Prerequisites (Build Once)

| Prerequisite | Benefits 4C | Benefits Autoresearch |
|---|---|---|
| `introduced_date` column + migration | Accurate trend bucketing | Accurate temporal train/val/test splits |
| GovInfo historical backfill (110-118) | Multi-session trend data | Training data (10K+ resolved bills/Congress) |
| Backfill sponsor/cosponsor data for historical bills | Legislator trend analysis | Strongest predictive features (bipartisan cosponsor patterns) |

## Architecture

```
legislative-research-tool/
├── src/                          # Existing platform (untouched by autoresearch)
│   ├── prediction/               # NEW (post-promotion only)
│   │   ├── model.py              # Production inference wrapper
│   │   ├── service.py            # Prediction service layer
│   │   └── schemas.py            # Pydantic response models
│   └── api/routers/prediction.py # NEW endpoint
├── autoresearch/                 # NEW: R&D sandbox (self-contained)
│   ├── prepare.py                # Fixed harness (human-maintained)
│   ├── train.py                  # Agent-modified model code
│   ├── program.md                # Research director instructions
│   ├── promote.py                # Bridge to src/prediction/
│   ├── experiments/              # Timestamped experiment logs
│   └── baselines/                # Reference implementations
└── migrations/versions/
    └── 008_add_introduced_date.py  # Shared prerequisite
```

## Resolved Questions

1. **How should prepare.py SQL adapt to actual schema vs. the roadmap schema?**
   **Decision:** Write prepare.py against the actual current schema from `src/models/`. Match real column names during initial setup to avoid surprises when running first experiments.

2. **Should the autoresearch dependencies (lightgbm, scikit-learn) go in pyproject.toml or a separate requirements file?**
   **Decision:** Separate `autoresearch/requirements.txt`. Keeps R&D dependencies fully isolated from the production platform install.

3. **What AUROC threshold triggers promotion to production?**
   **Decision:** Let it emerge from experimentation. Run experiments, see what's achievable with the available data, then set the promotion bar. Avoids premature commitment to a number that may not match data quality reality.

## Out of Scope

- State-level data backfill (deferred until federal experiments validate the loop)
- Frontend prediction UI (blocked on having a promoted model)
- LLM-enriched fields for historical bills (nice-to-have, not blocking baseline experiments)
- Phase 4B webhooks integration (independent workstream, no shared prereqs with autoresearch)
