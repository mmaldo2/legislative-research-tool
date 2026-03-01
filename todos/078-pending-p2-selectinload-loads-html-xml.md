---
status: pending
priority: p2
issue_id: "078"
tags: [code-review, performance, python, database]
dependencies: []
---

# selectinload Loads Unnecessary HTML/XML Columns

## Problem Statement

When loading bills with texts for analysis, `selectinload(Bill.texts)` loads all columns including `content_html` and `content_xml`, which can be very large. Only `content_text` is needed for LLM analysis.

## Findings

- **Source**: Performance Oracle
- **Location**: `src/api/analysis.py` — bill loading queries

## Proposed Solutions

### Option A: Use load_only on the relationship
```python
selectinload(Bill.texts).load_only(
    BillText.id, BillText.version_name, BillText.version_date, BillText.content_text
)
```
- **Pros**: Reduces memory usage significantly for large bills
- **Effort**: Small
- **Risk**: Low — need to ensure no code path accesses excluded columns

## Recommended Action

Option A.

## Technical Details

- **Affected files**: `src/api/analysis.py`

## Acceptance Criteria

- [ ] Bill text queries only load needed columns
- [ ] Memory usage reduced for large bills with HTML/XML content

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
