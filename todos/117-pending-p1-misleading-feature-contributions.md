---
status: pending
priority: p1
issue_id: "117"
tags: [code-review, prediction, correctness, quality]
dependencies: []
---

# Misleading Feature Contribution Heuristics in key_factors

## Problem Statement

The `_predict()` function in `src/prediction/service.py` (lines 313-322) computes "feature contributions" using hardcoded heuristics that don't reflect actual model weights. The `key_factors` in API responses are fabricated — they present arbitrary impact directions as model explanations. All 6 review agents flagged this.

## Findings

The heuristic multiplies raw feature **values** by `+1` (for 8 hand-picked features) or `-0.1` (everything else). This means:
- A bill with `title_length=200` shows "title_length" as a top factor purely because the raw value is large, not because the model cares about it.
- A genuinely important binary feature like `title_has_authoriz=1.0` will never surface because its raw value is small.
- The asymmetric multiplier (1.0 vs -0.1) artificially suppresses features not in the "positive" set.

API consumers who build UIs on `key_factors` will present misleading explanations to end users.

## Proposed Solutions

### Option A: Use LightGBM's built-in feature importance (Recommended)
Average `feature_importance(importance_type='gain')` across the 7 fold models. Pre-compute at model load time, serve as static importance ranking.
- **Pros:** 3 lines of code, genuinely meaningful, zero per-request cost
- **Cons:** Global importance, not per-prediction
- **Effort:** Small
- **Risk:** Low

### Option B: Use LightGBM's pred_contrib=True for per-prediction SHAP
Call `model.predict(data, pred_contrib=True)` to get tree-based SHAP contributions.
- **Pros:** Per-prediction explanations, model-truthful
- **Cons:** Slightly more latency, only covers LightGBM (not RF)
- **Effort:** Medium
- **Risk:** Low

### Option C: Remove key_factors until proper implementation
Make `key_factors` optional/empty, add back when SHAP is implemented.
- **Pros:** Honest — no fake explanations
- **Cons:** Less useful API response
- **Effort:** Small
- **Risk:** Low (API change)

## Recommended Action

Option A for immediate fix, Option B as follow-up.

## Technical Details

- **Affected files:** `src/prediction/service.py` lines 157-166, 312-323
- **Schema:** `src/prediction/schemas.py` — `key_factors` field

## Acceptance Criteria

- [ ] key_factors reflect actual model feature importance, not hardcoded heuristics
- [ ] Top factors are sensible for known bills (e.g., action_count matters more than title_length)
- [ ] No hardcoded +1/-0.1 multiplier in the codebase

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-18 | Created | Flagged by all 6 review agents on PR #25 |

## Resources

- PR #25: feat: ML prediction endpoint
- LightGBM docs: feature_importance(), pred_contrib
