---
status: complete
priority: p3
issue_id: "099"
tags: [code-review, performance]
dependencies: []
---

# Per-Bill SELECT During Ingestion

## Problem

Each ingester calls _get_old_values(bill_id) before each upsert = 1 SELECT per bill. With 15,000+ bills per Congress.gov ingestion, this doubles the query count.

## Files

- src/ingestion/base.py:38-40
- src/services/change_tracker.py:17-23

## Solution

Add a batch prefetch method to BaseIngester that loads tracked field values for a batch of bill IDs in a single IN(...) query. Apply per-page in each ingester.
