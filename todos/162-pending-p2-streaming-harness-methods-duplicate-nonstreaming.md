---
status: pending
priority: p2
issue_id: 162
tags: [code-review, architecture, dry]
dependencies: []
---

# 6 Streaming Harness Methods Duplicate Non-Streaming Counterparts

## Problem

`stream_summarize`, `stream_draft_policy_section`, `stream_rewrite_policy_section`, `stream_analyze_draft_constitutional`, `stream_analyze_draft_patterns` each duplicate ~30-50 lines of prompt construction identical to their non-streaming twins. ~195 lines of pure duplication.

## Fix

Extract prompt config into `_build_analysis_config()` shared by both `_run_analysis` and `_run_analysis_stream`. Or add `stream=False` parameter to `_run_analysis` itself.
