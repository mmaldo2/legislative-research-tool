---
status: pending
priority: p3
issue_id: 179
tags: [code-review, quality]
dependencies: [172]
---

# Inline Trivial _inherit_env Wrapper

## Problem Statement
`_inherit_env()` in `src/services/chat_service.py:378-384` is a 7-line function that only does `return dict(os.environ)`. It has its own test. This is unnecessary abstraction for a one-liner.

Note: This depends on #172 (env allowlist) — if allowlist is implemented, _inherit_env becomes non-trivial and should be kept.

## Proposed Solutions
### Option A: Inline at call site
- **Effort**: Small (5 min)
- Replace `_inherit_env()` call with `dict(os.environ)` at line 410
- Delete function and test

## Work Log
- 2026-03-22: Created from code review
