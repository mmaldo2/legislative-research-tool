---
status: complete
priority: p3
issue_id: "017"
tags: [code-review, quality]
dependencies: []
---

# Scheduler Has 3 Near-Identical Job Functions

## Problem Statement

`src/ingestion/scheduler.py` has three job functions (`_run_federal_ingestion`, `_run_state_ingestion`, `_run_legislators_ingestion`) that follow the exact same pattern: get session → create ingester → call ingest → handle error → close. This is copy-paste boilerplate.

## Findings

- **code-simplicity-reviewer**: Scheduler boilerplate, ~30 LOC reduction possible
- **architecture-strategist**: DRY violation

**Affected file:** `src/ingestion/scheduler.py`

## Proposed Solutions

### Option A: Generic runner function (Recommended)
```python
async def _run_ingestion(ingester_cls, **kwargs):
    async with async_session_factory() as session:
        ingester = ingester_cls(session, **kwargs)
        try:
            await ingester.ingest()
        except Exception as e:
            logger.error("Ingestion failed: %s", e)
        finally:
            await ingester.close()
```
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] Single generic runner replaces three duplicate functions
- [ ] All three scheduled jobs still work correctly
