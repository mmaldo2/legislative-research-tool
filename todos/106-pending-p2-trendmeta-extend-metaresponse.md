---
status: pending
priority: p2
issue_id: "106"
tags: [code-review, architecture, patterns]
dependencies: []
---

# TrendMeta Should Extend MetaResponse + Add Provenance Fields

## Problem Statement

`TrendMeta` in `src/schemas/trend.py` redefines `sources`, `last_updated`, and `total_count` instead of inheriting from the shared `MetaResponse` in `src/schemas/common.py`. This breaks the API meta contract and means trend responses lack `ai_enriched`, `ai_model`, and `ai_prompt_version` fields that other endpoints provide.

Additionally, `TrendSummaryResponse.confidence` lacks the `Field(ge=0.0, le=1.0)` constraint used by every other confidence field in the codebase.

## Findings

- **Architecture Strategist (VIOLATION)**: `TrendMeta` does not extend `MetaResponse`.
- **Architecture Strategist (VIOLATION)**: `TrendSummaryResponse` lacks provenance fields.
- **Pattern Recognition (P1)**: Confidence field missing `Field(ge=0.0, le=1.0)`.
- **Pattern Recognition (P1)**: `total_count` defaults to `0` (int) vs `None` (int | None) in MetaResponse.

**Affected file:** `src/schemas/trend.py`

## Proposed Solutions

### Option A: Inherit from MetaResponse (Recommended)
```python
from src.schemas.common import MetaResponse

class TrendMeta(MetaResponse):
    bucket: str = "month"
    group_by: str = "jurisdiction"
    date_from: str = ""
    date_to: str = ""
```
Add `confidence: float = Field(0.0, ge=0.0, le=1.0)` to `TrendSummaryResponse`.
Add `ai_model` and `ai_prompt_version` to `TrendSummaryResponse`, populated from harness.
- Effort: Small | Risk: Low

## Acceptance Criteria

- [ ] `TrendMeta` inherits from `MetaResponse`
- [ ] `TrendSummaryResponse.confidence` uses `Field(ge=0.0, le=1.0)`
- [ ] `TrendSummaryResponse` includes `ai_model` and `ai_prompt_version`
- [ ] Harness populates provenance fields in `generate_trend_narrative()`
