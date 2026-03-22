---
status: pending
priority: p3
issue_id: 165
tags: [code-review, architecture, yagni]
dependencies: []
---

# `_cached_or_stream()` is YAGNI — All Callers Skip Cache

## Problem

The `_cached_or_stream` method in harness.py checks the cache before streaming. But every streaming method in this diff passes `skip_store=True`, meaning the cache check is always skipped. The only method with `skip_store=False` (`stream_summarize`) is not called by any endpoint. This violates YAGNI.

## Fix

Remove `_cached_or_stream`. Each streaming method can call `_run_analysis_stream` directly. Add cache support later if needed.
