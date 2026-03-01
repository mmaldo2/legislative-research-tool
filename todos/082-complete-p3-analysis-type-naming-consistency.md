---
status: pending
priority: p3
issue_id: "082"
tags: [code-review, quality, python, naming]
dependencies: []
---

# analysis_type Naming Inconsistency + Outdated Endpoint Description

## Problem Statement

Two naming issues:
1. Existing analysis types (`summary`, `topics`, `comparison`) are single-word nouns. New types (`version_diff`, `constitutional`, `pattern_detect`) use snake_case compounds and mixed parts of speech.
2. The `list_analyses` endpoint description still says "classification" but the actual stored type is "topics".

## Findings

- **Source**: Architecture Strategist
- **Location**: `src/llm/harness.py`, `src/api/analysis.py:309`

## Proposed Solutions

### Option A: Document canonical values + fix description
- Update endpoint description to list all valid types
- Add a comment documenting the naming convention
- Consider a StrEnum for compile-time safety (see todo 079 overlap)
- **Effort**: Small

## Acceptance Criteria

- [ ] `list_analyses` endpoint description lists all valid analysis_type values
- [ ] analysis_type values documented

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
