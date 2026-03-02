---
status: pending
priority: p3
issue_id: "116"
tags: [code-review, quality, cleanup]
dependencies: []
---

# Minor Cleanups — last_updated, Logger, Cache-Control, Hardcoded Sources

## Problem Statement

Several minor issues identified across reviewers that individually don't warrant separate todos.

## Findings

1. **`TrendMeta.last_updated` never populated** (Python Reviewer, Agent-Native): Either populate with `MAX(updated_at)` from the underlying table, or remove the field.

2. **Logger defined but never used** (Pattern Recognition): `logger = logging.getLogger(__name__)` at line 21 of `trend_service.py` is never called. Add cache hit/miss logging or remove.

3. **No Cache-Control headers** (Agent-Native): Responses include no `Cache-Control: max-age=300` header. Agents can't respect caching semantics.

4. **Hardcoded sources list repeated 3 times** (Simplicity): `["govinfo", "openstates", "legiscan"]` at lines 104, 182, 282. Extract to module constant.

5. **`period_totals.get(period_str, 1)` masks bugs** (Python Reviewer): Using `1` as default denominator silently produces wrong percentages. Use direct key access — `KeyError` means a programming bug.

6. **Summary endpoint hardcodes `group_by="jurisdiction"`** (Agent-Native): The summary should accept a `group_by` parameter consistent with other trend endpoints.

## Acceptance Criteria

- [ ] `last_updated` either populated or removed
- [ ] Logger used for cache hit/miss logging (or removed)
- [ ] Sources list extracted to module constant
- [ ] `period_totals.get(period_str, 1)` changed to direct key access
