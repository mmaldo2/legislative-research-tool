---
status: complete
priority: p2
issue_id: "090"
tags: [code-review, security, api]
dependencies: []
---

# Untyped criteria Dict on SavedSearchCreate

## Problem

SavedSearchCreate.criteria is `dict` with no schema validation. Accepts arbitrary JSON including oversized objects. The _matches_criteria evaluator only reads jurisdiction_id, status, query but this is not enforced.

## Files

- src/schemas/saved_search.py:11-14
- src/services/alert_evaluator.py:109-126

## Solution

Define a typed `SearchCriteria` Pydantic model with validated fields (query max_length=500, jurisdiction_id, status, mode) and `extra="forbid"`. Use it in SavedSearchCreate and _matches_criteria.
