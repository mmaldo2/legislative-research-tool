---
status: pending
priority: p2
issue_id: "072"
tags: [code-review, bug, python, schema]
dependencies: []
---

# has_severability_clause on Wrong Model (VersionDiffOutput)

## Problem Statement

`has_severability_clause: bool = False` exists on `VersionDiffOutput` at `src/schemas/analysis.py:73`. This field belongs only on `ConstitutionalAnalysisOutput` (where it also appears at line 92). A version diff would not assess severability — this is copy-paste contamination.

## Findings

- **Source**: Architecture Strategist, Code Simplicity Reviewer, Python Reviewer
- **Location**: `src/schemas/analysis.py:73`
- **Evidence**: The `version_diff_v1.py` prompt does not mention severability analysis

## Proposed Solutions

### Option A: Remove from VersionDiffOutput
- Delete the `has_severability_clause` field from `VersionDiffOutput`
- Keep it only on `ConstitutionalAnalysisOutput`
- Remove corresponding field from frontend `VersionDiffOutput` interface
- **Pros**: Correct schema, no misleading data
- **Effort**: Small
- **Risk**: None (field always defaults to False, so no data loss)

## Recommended Action

Option A.

## Technical Details

- **Affected files**: `src/schemas/analysis.py`, `frontend/src/types/api.ts`

## Acceptance Criteria

- [ ] `has_severability_clause` removed from `VersionDiffOutput`
- [ ] Field remains on `ConstitutionalAnalysisOutput`
- [ ] Frontend type updated accordingly

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
