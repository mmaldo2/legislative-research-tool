---
status: pending
priority: p2
issue_id: "121"
tags: [code-review, prediction, architecture, quality]
dependencies: ["119"]
---

# Refactor Model State: Lazy Loading, Dataclass, Typed Returns

## Problem Statement

`src/prediction/service.py` uses 6 mutable module-level globals, loads models at import time (causing CI noise and making the module non-optional), and returns untyped dicts. Multiple agents flagged overlapping issues with this pattern.

## Findings

1. **Import-time side effect** (lines 76): `_load_models()` at module scope triggers disk I/O and pickle deserialization during test collection, IDE indexing, and any transitive import. Models are gitignored, so this always fails in CI.
2. **6 mutable globals** (lines 22-27): Managed via `global` keyword, untestable without monkeypatching.
3. **Untyped return** (line 94): `predict_bill()` returns `dict | None` — forces string-key access in endpoint.
4. **Ambiguous None** (lines 100-101 vs 148-149): `None` means both "model not loaded" and "bill not found".
5. **Inline imports** (lines 179, 219): `import math` and `import re` inside function body.

## Proposed Solutions

### Option A: Dataclass + lazy loading (Recommended)
```python
@dataclass(frozen=True)
class ModelBundle:
    lgbm_models: list[lgb.Booster]
    rf_models: list
    meta_lr: object
    meta_scaler: object
    metadata: dict[str, Any]

_model: ModelBundle | None = None

def _ensure_loaded() -> ModelBundle | None:
    global _model
    if _model is None:
        _model = _load_models()  # returns ModelBundle or None
    return _model
```
- Move `import math`, `import re` to top of file
- Return typed result from `predict_bill` (dataclass or PredictionResponse)
- Raise `ModelNotLoadedError` instead of returning None for model state
- **Effort:** Medium
- **Risk:** Low

## Acceptance Criteria

- [ ] No `_load_models()` call at module scope
- [ ] Model state in a single dataclass, no `global` keyword
- [ ] `predict_bill` returns a typed object, not a dict
- [ ] Model-not-loaded raises an exception, bill-not-found returns None
- [ ] `math` and `re` imported at top of file

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-18 | Created | Python, Architecture, Simplicity reviewers all flagged |
