---
status: complete
priority: p2
issue_id: "013"
tags: [code-review, bug]
dependencies: []
---

# MetaResponse Provenance Fields Never Populated

## Problem Statement

The `MetaResponse` schema defines provenance fields (`source`, `last_updated`, `ai_model`, `confidence`) per CLAUDE.md's "Every API response includes provenance metadata" pattern, but no endpoint actually populates these fields. They're always None/default.

## Findings

- **agent-native-reviewer (CRITICAL)**: MetaResponse provenance never populated
- **code-simplicity-reviewer**: MetaResponse is bloated with unused fields

**Affected files:**
- `src/schemas/` — MetaResponse definition
- All API route files — responses don't include provenance

## Proposed Solutions

### Option A: Populate provenance in responses (Recommended)
- Add source, last_updated, model info to API responses
- Create a utility to build MetaResponse from query results
- **Effort**: Medium
- **Risk**: Low

### Option B: Remove MetaResponse until needed
- Remove unused abstraction, add back when provenance is actually implemented
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] API responses include populated provenance metadata
- [ ] Source attribution (which data source provided the data) is accurate
- [ ] AI-generated content includes model version and confidence
