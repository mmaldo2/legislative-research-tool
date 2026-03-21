---
status: pending
priority: p2
issue_id: "077"
tags: [code-review, validation, python, schema]
dependencies: []
---

# Confidence Fields Lack Bounds Validation

## Problem Statement

Multiple output schemas have `confidence: float` fields without `Field(ge=0.0, le=1.0)` constraints. The LLM could return values outside [0, 1] that propagate to the frontend.

## Findings

- **Source**: Python Reviewer
- **Location**: `src/schemas/analysis.py` — `VersionDiffOutput.confidence`, `ConstitutionalAnalysisOutput.confidence`, `PatternDetectionOutput.confidence`, `PatternDetectionOutput.model_legislation_confidence`

## Proposed Solutions

### Option A: Add Field bounds
- `confidence: float = Field(ge=0.0, le=1.0)`
- **Pros**: Validates LLM output, prevents invalid data
- **Effort**: Small
- **Risk**: Low — LLM might occasionally return > 1.0, which would fail parsing and trigger fallback

## Recommended Action

Option A.

## Technical Details

- **Affected files**: `src/schemas/analysis.py`

## Acceptance Criteria

- [ ] All confidence fields have `ge=0.0, le=1.0` bounds
- [ ] Existing schemas (`BillSummaryOutput`, etc.) also updated for consistency

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
