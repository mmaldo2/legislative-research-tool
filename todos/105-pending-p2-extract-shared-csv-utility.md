---
status: pending
priority: p2
issue_id: "105"
tags: [code-review, architecture, dry]
dependencies: ["104"]
---

# Extract Shared CSV Sanitization Utility

## Problem Statement

`_sanitize_csv()`, `_CSV_FORMULA_RE`, and the CSV response pattern are copy-pasted verbatim between `src/api/trends.py` and `src/api/export.py`. If the sanitization logic is updated in one but not the other, a security vulnerability could be partially fixed.

## Findings

- **Architecture Strategist**: DRY violation — extract to shared utility.
- **Code Simplicity Reviewer**: ~15 LOC duplication across modules.
- **Pattern Recognition**: Duplicated in both files identically.

**Affected files:**
- `src/api/trends.py` lines 25-52
- `src/api/export.py` lines 20-28

## Proposed Solutions

### Option A: Extract to `src/utils/csv.py` (Recommended)
Create a shared module with `sanitize_csv()`, `CSV_FORMULA_RE`, and `csv_response()`. Import from both `trends.py` and `export.py`.
- Effort: Small | Risk: Low

## Acceptance Criteria

- [ ] Shared CSV utility module created
- [ ] Both `trends.py` and `export.py` import from shared module
- [ ] No duplicated CSV sanitization code remains
