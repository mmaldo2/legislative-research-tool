---
status: pending
priority: p2
issue_id: "011"
tags: [code-review, performance]
dependencies: ["006"]
---

# Unbounded BM25 Index Loads All Bills Into Memory

## Problem Statement

`BM25Index.build()` fetches ALL bills from the database and loads them into memory. With tens of thousands of bills, this will consume significant RAM and take a long time to build.

## Findings

- **performance-oracle (CRITICAL)**: Unbounded data load
- **code-simplicity-reviewer**: Over-engineering risk if index is rarely used

**Affected file:** `src/search/bm25.py`

## Proposed Solutions

### Option A: Pagination + streaming build (Recommended)
- Use `yield_per()` or paginated queries to stream bills
- Build index incrementally
- Set a configurable max corpus size
- **Effort**: Medium
- **Risk**: Low

### Option B: Limit scope
- Only index recent session bills or user-specified jurisdictions
- **Effort**: Small
- **Risk**: Reduced search coverage

## Acceptance Criteria

- [ ] BM25 build doesn't load all bills at once
- [ ] Memory usage is bounded
- [ ] Build time is reasonable for 50K+ bills
