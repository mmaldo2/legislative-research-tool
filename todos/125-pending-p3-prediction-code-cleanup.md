---
status: pending
priority: p3
issue_id: "125"
tags: [code-review, prediction, quality, cleanup]
dependencies: ["121"]
---

# Prediction Code Cleanup — Miscellaneous P3 Items

## Problem Statement

Several minor issues identified across reviewers that individually don't warrant separate todos.

## Findings

1. **`__import__("pandas")` hack in promote.py** (line 36): Obfuscated — pandas is already an indirect dependency. Replace with `import pandas as pd` at top of file.

2. **promote.py relative path** (line 25): `Path("../src/prediction/models")` only works from `autoresearch/` directory. Change to `Path(__file__).resolve().parent.parent / "src" / "prediction" / "models"`.

3. **Test coverage gaps** (`test_prediction.py`): No tests for `_build_single_bill_features` (the most complex pure function — date arithmetic, regex, 18 features) or `_predict`. `test_probability_bounds` catches `Exception` instead of `ValidationError`.

4. **Repeated dependency_overrides boilerplate** in tests (lines 56-63, 71-78, 95-108): Every test manually sets/clears `app.dependency_overrides`. Extract to a pytest fixture.

5. **Feature names list recreated per call** (service.py:262-281): Should be a module-level constant `_FEATURE_NAMES`.

6. **Feature values/names parallel lists drift risk** (service.py:241-281): Could merge into list of (name, value) tuples.

## Acceptance Criteria

- [ ] promote.py uses proper import and __file__-based path
- [ ] _build_single_bill_features has unit tests with known inputs/outputs
- [ ] Test fixtures reduce boilerplate
- [ ] Feature names extracted to module constant

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-18 | Created | Multiple reviewers, consolidated P3 items |
