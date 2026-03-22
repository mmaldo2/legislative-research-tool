---
status: resolved
priority: p1
issue_id: "119"
tags: [code-review, prediction, correctness, architecture]
dependencies: []
---

# Feature Computation Parity Risk Between train.py and service.py

## Problem Statement

Feature computation is duplicated between `autoresearch/train.py::build_features()` (pandas batch) and `src/prediction/service.py::_build_single_bill_features()` (single-row Python). There is no automated validation that they produce the same output. Any future feature change requires synchronized edits in two files with no safety net. Architecture reviewer rated this P0.

## Findings

1. **Latent congress_number bug:** `train.py` uses regex `r"us-(\d+)"` while `service.py` uses `session_id.split("-")[1]`. These agree for `us-118` but diverge for state-level IDs like `ny-2023-2024` (regex → 0.0, split → 2023.0).

2. **No feature name validation on model load:** `metadata.json` records `feature_names` but `_load_models()` never checks they match what `_build_single_bill_features()` produces.

3. **Magic index fallbacks:** `_predict()` lines 294-296 use hardcoded defaults (4, 1, 16) for meta-feature indices. If metadata is missing these keys, wrong feature indices are used silently.

## Proposed Solutions

### Option A: Parity test + validation (Recommended)
1. Fix `congress_number` in service.py to use the same regex as train.py.
2. Add assertion in `_load_models()` that `metadata["feature_names"]` matches the feature names list.
3. Remove magic index fallbacks — fail loudly if metadata is incomplete.
4. Add a test that feeds a known row through both code paths and asserts identical feature vectors.
- **Effort:** Medium
- **Risk:** Low

### Option B: Shared feature module (longer-term)
Extract feature computation to a shared module imported by both train.py and service.py, with adapters for pandas batch vs. single-row.
- **Effort:** Large
- **Risk:** Medium (changes autoresearch contract)

## Acceptance Criteria

- [ ] congress_number extraction uses regex in service.py
- [ ] Model load validates feature_names match
- [ ] No magic fallback defaults for meta-feature indices
- [ ] Test verifies feature parity for a known bill row

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-18 | Created | Architecture reviewer rated P0, all agents flagged duplication risk |
