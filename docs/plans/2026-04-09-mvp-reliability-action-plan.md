# MVP Reliability Action Plan

Goal: turn the current investigation-first legislative research app into a reliable daily-usable MVP by fixing the broken synthesis path first, then tightening investigation continuity, then establishing an autonomous QA/improvement loop.

Context:
- Live review confirmed the strongest product center is: Investigations -> Search -> Save bills -> Compare -> Ask Assistant -> Generate Memo.
- Browse/search/save mostly works.
- Highest-value failures today are in assistant/report reliability and similar-bills backend stability.
- Local/dev setup is also brittle because runtime dependencies are split across pyproject, autoresearch requirements, and the Claude SDK fallback path.

Primary findings to address first:
1. Assistant and report generation fail because the Claude SDK fallback path is not reliably installed/configured.
2. Similar-bills lookup fails because the code expects `bill_embeddings.embedding` while the live database currently exposes `bill_embeddings.vector`, and fallback handling does not rollback the aborted transaction.
3. Investigation continuity still leaks context in a few places, and frontend env/API helper code contains corrupted API key constants that should be cleaned up.

---

## Phase 1: Restore core reliability

### Task 1: Make the Claude SDK fallback a declared runtime dependency
Files:
- Modify: `pyproject.toml`

Changes:
- Add the Claude Agent SDK package to the main project dependency set because local/dev runtime currently depends on it when `ANTHROPIC_API_KEY` is absent.
- Keep the app’s documented fallback path aligned with actual install behavior.

Verification:
- Fresh `uv pip install -e '.[dev]'` should include the SDK.
- LLM-powered endpoints should no longer fail with `ModuleNotFoundError: claude_agent_sdk`.

### Task 2: Improve LLM fallback failure behavior
Files:
- Modify: `src/api/deps.py`
- Modify: `src/llm/claude_sdk_adapter.py` if needed

Changes:
- Ensure the fallback path either works or fails with a clear operator-facing message, not a generic 500.
- Keep current behavior compatible with API key mode and local Claude SDK mode.

Verification:
- Report or assistant requests should either succeed or return a clear setup/config error.

### Task 3: Fix corrupted frontend API key constants
Files:
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/sse.ts`

Changes:
- Replace the corrupted `API_KEY=proces..._KEY` lines with the intended `process.env.NEXT_PUBLIC_API_KEY ?? ""` constant.
- Keep client header behavior intact.

Verification:
- Frontend dev server still runs.
- API and SSE requests continue to work.

### Task 4: Fix similar-bills schema drift and fallback transaction handling
Files:
- Modify: `src/search/vector.py`
- Add tests: `tests/test_search/test_vector.py`

Changes:
- Detect the actual pgvector column name (`vector` vs `embedding`) instead of assuming one schema.
- Roll back the SQLAlchemy session after the primary query fails so the fallback query can execute.
- Preserve current API behavior and return fallback matches when embeddings are unavailable or schema differs.

Verification:
- `GET /api/v1/bills/{bill_id}/similar` returns 200 instead of 500.
- New tests cover column-name handling and rollback-before-fallback behavior.

---

## Phase 2: Tighten the investigation workflow

### Task 5: Preserve investigation context consistently
Files likely:
- `frontend/src/app/collections/[id]/page.tsx`
- `frontend/src/app/bills/[id]/page.tsx`
- `frontend/src/app/search/page.tsx`
- related link helpers/components

Changes:
- Thread `collection_id` through all “Continue Search”, bill-detail, compare, assistant, and report links.
- Prevent users from falling out of the active investigation loop.

Verification:
- Clicking through from an investigation preserves the active context everywhere it should.

### Task 6: Make search triage faster
Files likely:
- `frontend/src/app/search/search-results.tsx`
- `frontend/src/lib/api.ts`

Changes:
- Add direct “Add to Investigation” actions from results.
- Reduce the need to open every bill detail page just to build a working set.

Verification:
- A user can add multiple relevant bills from search with fewer clicks.

---

## Phase 3: Establish the daily autonomous QA/improvement loop

Goal:
Run a recurring agent-driven loop that exercises the live app, captures concrete failures, and feeds those failures into a repair workflow.

### Proposed loop design

1. QA runner job
- Frequency: daily on weekdays, optionally more often during active development.
- Action: open the live app and exercise core flows using browser automation.
- Target flows:
  - create/open investigation
  - search with and without investigation context
  - open bill detail
  - add to investigation
  - compare similar bills
  - ask assistant a question
  - generate memo/report
- Output:
  - timestamped markdown error report in repo or local ops folder
  - screenshots for broken states
  - categorized failures: setup, backend 5xx, UI regression, empty-state quality issue, latency/timeouts

2. Triage agent job
- Reads the latest error report.
- Deduplicates recurring failures.
- Converts them into a prioritized fix list.
- Can optionally open/update a daily issue note or append to a standing QA ledger.

3. Repair loop
- Either:
  - notify us with the prioritized failures for supervised fixes, or
  - automatically start a constrained fix pass on pre-approved bug classes (safe frontend/backend bugfixes only).

4. Verification job
- Re-runs the same QA flow after changes.
- Confirms whether the failure was resolved or regressed.

### Guardrails
- Keep the QA job read-mostly except for approved test data creation (for example, a dedicated QA investigation name prefix).
- Store reports in a stable folder like `docs/qa/` or `.hermes/qa/`.
- Avoid autonomous broad refactors; restrict auto-fix agents to scoped bugfixes.
- Require human review before merges or before changing product behavior materially.

### First implementation slice for the loop
- Add a browser-driven QA script or Hermes cron job that runs the 5-6 canonical flows daily.
- Save a markdown report plus screenshots.
- Deliver summary to origin/Telegram.
- Use the report as input to the next bugfix session.

---

## Immediate execution order
1. Fix runtime dependency/setup issues for assistant and reports.
2. Fix similar-bills backend failure.
3. Run targeted verification.
4. Then wire the autonomous QA loop.

## Success criteria for this pass
- Assistant no longer fails with missing Claude SDK dependency.
- Report generation no longer fails because of missing fallback runtime package.
- Similar bills endpoint no longer 500s on the current database schema.
- Frontend API/SSE helper constants are cleaned up.
- A concrete design exists for the daily autonomous QA/improvement loop.
