---
status: pending
priority: p2
issue_id: 159
tags: [code-review, data-integrity, streaming]
dependencies: []
---

# Streaming Compose Stores Empty Provenance Sources

## Problem

The sync `compose_section()` computes `provenance_sources` from `result.source_bill_ids` for draft/rewrite actions. The streaming variant hard-codes `"sources": []`. Generations created via streaming have no source attribution. If accepted, sections lose provenance data permanently.

## Fix

Compute and store provenance the same way the sync path does, after the done event metadata is available.
