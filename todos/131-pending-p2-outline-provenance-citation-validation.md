---
status: complete
priority: p2
issue_id: "131"
tags: [code-review, composer, backend, provenance, llm]
dependencies: []
---

# Reject Mixed Invalid Outline Citations Instead of Silently Rewriting Provenance

## Problem Statement

Phase 2 treats outline provenance as a first-class drafting artifact, but the enrichment logic currently accepts mixed valid and invalid `source_bill_ids` from the model. It filters out the invalid IDs and then reuses the filtered index to attach `source_notes`, which can shift a note onto the wrong cited bill. That produces misleading provenance instead of failing fast.

## Findings

1. **`_enrich_outline_payload()` filters bill IDs after the model response is parsed** in `src/services/policy_composer_service.py:145-150`.
2. **The code only raises when no valid citations remain**, so responses with a mix of valid and invalid IDs are still accepted (`src/services/policy_composer_service.py:151-154`).
3. **`source_notes` are indexed against the filtered list**, not the original `(bill_id, note)` pairs, so a dropped invalid ID can misalign the remaining notes (`src/services/policy_composer_service.py:157-159`).
4. **The resulting provenance is surfaced directly in the composer UI**, so the user sees the corrupted attribution as if it were trustworthy.

## Proposed Solutions

### Option A: Treat any invalid cited bill ID as an outline-generation failure (Recommended)
1. Validate that every `source_bill_id` exists in the selected precedent set.
2. Raise `OutlineGenerationError` if any invalid citation appears.
3. Add a test for a mixed valid/invalid citation list and assert that no outline is accepted.
- Effort: Small
- Risk: Low

### Option B: Preserve bill/note pairing explicitly
1. Iterate over the original `source_bill_ids` with their note positions intact.
2. Only keep exact valid pairs, without reindexing notes onto surviving IDs.
3. Still log or reject unexpected invalid IDs so provenance drift is visible.
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] Mixed valid/invalid `source_bill_ids` no longer produce accepted outline payloads silently
- [ ] `source_notes` remain aligned with the original cited bill IDs
- [ ] Tests cover invalid-only and mixed-validity citation responses
- [ ] Composer provenance UI reflects only verified, correctly paired citations

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-20 | Created | Found during Phase 1/2 composer review |
