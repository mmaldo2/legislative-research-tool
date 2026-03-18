---
title: "feat: Promote prediction model to production API"
type: feat
status: active
date: 2026-03-18
origin: docs/brainstorms/2026-03-17-autoresearch-integration-brainstorm.md
---

# feat: Promote Prediction Model to Production API

## Overview

Wire the autoresearch bill outcome prediction model (AUROC 0.997 on held-out 2024 data) into the production API as `GET /bills/{id}/prediction`. Three pieces: `promote.py` exports the model, `src/prediction/` loads and serves it, and a new API endpoint returns predictions with explainability.

## Problem Statement

The autoresearch module produced a validated stacking ensemble (LightGBM + RandomForest + LogisticRegression) that predicts committee passage with 99.7% AUROC. But it only runs as a CLI script. Researchers using the platform can't see predictions — the model needs to be accessible via the API and eventually the frontend.

## Proposed Solution

### 1. `autoresearch/promote.py` — Export Model Artifact

Retrain the best model (Experiment 8 architecture) on train+val combined, save all components:

```python
# promote.py exports:
# - models/lgbm_folds/fold_{n}.txt  (7 LightGBM fold models)
# - models/rf_folds/fold_{n}.pkl    (7 RandomForest fold models)
# - models/meta_lr.pkl              (LogisticRegression meta-learner)
# - models/meta_scaler.pkl          (StandardScaler for meta-features)
# - models/metadata.json            (feature names, training date, metrics)
```

Output directory: `src/prediction/models/` (gitignored — model artifacts are large).

### 2. `src/prediction/service.py` — Prediction Service

```python
# Key responsibilities:
# 1. Load model artifacts at import time (module-level singleton)
# 2. Build features for a single bill from DB (same logic as train.py)
# 3. Run inference through the stacking pipeline
# 4. Return probability + top feature contributions

async def predict_bill(session: AsyncSession, bill_id: str) -> PredictionResult:
    """Score a single bill. Returns None if bill not found or model not loaded."""
```

Feature computation queries the same tables as `prepare.py` but for a single bill:
- `bills` — title, classification, identifier, introduced_date, status
- `sessions` — start_date, end_date (for session_position)
- `bill_actions` — action_count, first/last action dates
- `sponsorships` + `people` — cosponsor_count, bipartisan count, sponsor party

### 3. `src/api/prediction.py` — API Endpoint

```
GET /bills/{bill_id}/prediction

Response 200:
{
  "bill_id": "abc123",
  "committee_passage_probability": 0.34,
  "model_version": "2026-03-18",
  "key_factors": [
    {"feature": "action_count", "value": 12, "impact": "positive"},
    {"feature": "cosponsor_count", "value": 45, "impact": "positive"},
    {"feature": "session_position", "value": 0.15, "impact": "positive"}
  ],
  "base_rate": 0.038,
  "meta": { ... MetaResponse fields ... }
}

Response 404: Bill not found
Response 503: Model not loaded
```

## Technical Considerations

**Feature computation at request time:** The service queries current bill data on each request. No caching — bills accumulate actions over time, so predictions naturally update as legislative activity progresses. This is the "early warning system" behavior.

**Model loading:** Load once at module import, not per-request. The LightGBM models are text files (~100KB each), RF models are pickled (~5MB each). Total model footprint ~40MB in memory. Acceptable for a single-process API.

**Feature parity:** The service must compute the exact same 18 features as `train.py:build_features()`. Extract the feature logic into a shared function or duplicate it (duplication is acceptable since the autoresearch sandbox is intentionally decoupled).

**Explainability:** Use LightGBM's `predict(X, pred_contrib=True)` for SHAP-like feature contributions. This tells the user *why* the model made its prediction — "action_count is the biggest positive factor" etc. The `key_factors` response field surfaces the top 5 contributing features.

**Graceful degradation:** If model files don't exist (fresh deploy, not yet promoted), the endpoint returns 503 with a clear message. The rest of the API continues to work.

## Acceptance Criteria

- [ ] `autoresearch/promote.py` exports model artifacts to `src/prediction/models/`
- [ ] `src/prediction/__init__.py` exists
- [ ] `src/prediction/service.py` loads model at module level, exposes `predict_bill(session, bill_id)`
- [ ] `src/prediction/schemas.py` defines `PredictionResponse` extending `MetaResponse`
- [ ] `src/api/prediction.py` registers `GET /bills/{bill_id}/prediction` endpoint
- [ ] Endpoint mounted in `src/api/app.py` with pro+ auth tier
- [ ] Rate limited at 30/minute (matching trends endpoint pattern)
- [ ] Returns 404 for unknown bill_id, 503 if model not loaded
- [ ] `key_factors` includes top 5 feature contributions with direction
- [ ] `base_rate` field shows overall positive rate for context
- [ ] Model files gitignored (`src/prediction/models/` in .gitignore)
- [ ] Tests: endpoint with mocked service, 404/503 error cases, schema validation
- [ ] `metadata.json` includes training date, AUROC, feature names, and threshold

## Files to Create

| File | Purpose |
|---|---|
| `autoresearch/promote.py` | Retrain best model, export artifacts |
| `src/prediction/__init__.py` | Package init |
| `src/prediction/service.py` | Model loading + single-bill inference |
| `src/prediction/schemas.py` | Pydantic response models |
| `src/api/prediction.py` | FastAPI endpoint |
| `tests/test_api/test_prediction.py` | Endpoint tests |

## Files to Modify

| File | Change |
|---|---|
| `src/api/app.py` | Mount prediction router with pro+ auth |
| `.gitignore` | Add `src/prediction/models/` |

## Sources & References

- Autoresearch brainstorm: `docs/brainstorms/2026-03-17-autoresearch-integration-brainstorm.md`
- Autoresearch plan (Phase 3): `docs/plans/2026-03-17-feat-autoresearch-bill-prediction-plan.md`
- Best model: `autoresearch/train.py` (Experiment 8 — stacking ensemble)
- Existing LLM prediction: `src/api/analysis.py:333-394`, `src/schemas/analysis.py:149-170`
- Router mounting pattern: `src/api/app.py:72-105`
- Service pattern: `src/services/trend_service.py`
- Related PRs: #20 (autoresearch prerequisites), #21 (detail enrichment), #22 (concurrent enrichment)
