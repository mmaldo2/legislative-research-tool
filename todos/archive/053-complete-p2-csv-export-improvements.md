---
status: complete
priority: p2
issue_id: "053"
tags: [code-review, performance, security]
dependencies: []
---

# CSV Export: Not Streaming + 404 for Empty + Formula Injection

## Problem Statement

Three issues with the CSV export endpoint: (1) builds entire CSV in memory despite using StreamingResponse, (2) returns 404 for empty results instead of empty CSV, (3) no sanitization against spreadsheet formula injection.

## Findings

1. `StringIO` buffer built entirely in memory, then wrapped in `iter([output.getvalue()])` — not streaming (`src/api/export.py` lines 61-105)
2. 404 for "no bills match" — semantically incorrect, should return empty CSV with headers (`src/api/export.py` line 57)
3. Bill titles/subjects written to CSV without escaping leading `=`, `+`, `-`, `@` chars — formula injection risk
4. Agents: Performance Oracle (CRITICAL-1), Security Sentinel (H4), Architecture Strategist (O, P), Simplicity Reviewer (#8)

## Proposed Solutions

### Option A: Fix all three (Recommended)
- Return 200 with headers-only CSV when no results (remove the 404)
- Sanitize CSV values: prepend `'` to cells starting with `=+\-@\t\r`
- Optionally: true chunked streaming (nice-to-have given 5K cap)
- **Effort**: Small
- **Risk**: Low

## Technical Details

- **Files**: `src/api/export.py`

## Acceptance Criteria

- [ ] Empty result set returns 200 with CSV headers only
- [ ] CSV values are sanitized against formula injection
- [ ] Export works correctly with include_summary=True

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
