---
status: pending
priority: p3
issue_id: "020"
tags: [code-review, quality]
dependencies: []
---

# F-Strings Used in Logging Calls

## Problem Statement

Several files use f-strings in logging calls (e.g., `logger.info(f"Starting {x}")`) instead of lazy `%`-style formatting (e.g., `logger.info("Starting %s", x)`). F-strings are evaluated even when the log level is disabled, wasting CPU.

## Findings

- **kieran-python-reviewer (MEDIUM)**: f-strings in logging

**Affected files:** `src/cli.py`, various ingestion files

## Proposed Solutions

### Option A: Convert to %-style logging (Recommended)
- Replace `logger.info(f"...")` with `logger.info("...", arg)`
- **Effort**: Small
- **Risk**: None

## Acceptance Criteria

- [ ] No f-strings in logging calls
- [ ] All logging uses lazy %-style formatting
