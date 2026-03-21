---
status: pending
priority: p3
issue_id: "079"
tags: [code-review, types, typescript, python]
dependencies: []
---

# String Literal Types for Known Enums

## Problem Statement

Several fields use bare `string`/`str` types where the values are known enums: severity (`"high" | "moderate" | "low"`), pattern_type (`"identical" | "adapted" | "inspired" | "coincidental"`), overall_risk_level, change significance. Using literal types improves type safety and IDE autocompletion.

## Findings

- **Source**: TypeScript Reviewer, Python Reviewer
- **Location**: `frontend/src/types/api.ts`, `src/schemas/analysis.py`

## Proposed Solutions

### Option A: Add Literal/union types
- Python: `severity: Literal["high", "moderate", "low"]`
- TypeScript: `severity: "high" | "moderate" | "low"`
- **Effort**: Small

## Acceptance Criteria

- [ ] Known enum fields use literal/union types in both Python and TypeScript

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
