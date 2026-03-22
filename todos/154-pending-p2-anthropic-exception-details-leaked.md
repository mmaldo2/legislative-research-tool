---
status: pending
priority: p2
issue_id: 154
tags: [code-review, security, streaming]
dependencies: []
---

# Anthropic SDK Exception Details Leaked to Client

## Problem

`_run_analysis_stream` in harness.py catches Anthropic exceptions and includes `"detail": str(e)` in SSE error events. Exception strings can contain internal URLs, headers, and error messages.

## Fix

Remove `"detail": str(e)`, log full exception server-side, emit only user-safe messages.
