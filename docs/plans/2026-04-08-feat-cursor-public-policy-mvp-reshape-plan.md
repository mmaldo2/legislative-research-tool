# Cursor for Public Policy MVP Reshape Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Reshape the current legislative-research-tool UI and product surface around an investigation-first MVP: search -> save working set -> compare -> ask follow-up questions -> generate research output.

**Architecture:** Reuse the strongest existing substrate — search, bill detail, compare, collections, reports, and chat — but recast them into a coherent investigation workspace. Do not build a new platform layer first. Instead, treat existing collections as the first implementation scaffold for investigations, make chat and outputs collection-aware, and demote drafting/platform features from primary navigation.

**Tech Stack:** Next.js App Router, TypeScript, shadcn/ui, FastAPI, existing collections/chat/report/search APIs, OpenAPI-generated types.

---

## Why this reshape is needed

The current app exposes many powerful capabilities, but the visible IA is still feature/tool oriented:
- `/search`
- `/collections`
- `/composer`
- `/reports`
- `/assistant`
- `/bills/[id]`
- `/compare`
- `/jurisdictions`
- `/legislators`

The MVP spec calls for a different center of gravity:
- the unit of value is the investigation, not the bill
- the assistant should work primarily over the active working set
- outputs should be generated from saved investigation context
- drafting/composer should remain available, but not define the product story

This plan refines the product down from the current breadth and reuses what already exists.

---

## Current codebase facts to preserve

### Existing frontend surfaces
- `frontend/src/app/page.tsx` — currently positioned as "The Policy Drafting IDE"
- `frontend/src/components/site-header.tsx` — primary nav currently emphasizes Search / Jurisdictions / Legislators / Collections / Composer / Reports / Assistant
- `frontend/src/app/search/page.tsx` — already a strong search landing page
- `frontend/src/app/collections/page.tsx` and `frontend/src/app/collections/[id]/page.tsx` — existing working-set primitive
- `frontend/src/app/bills/[id]/page.tsx` — rich bill detail page with tabs
- `frontend/src/app/assistant/page.tsx` — global assistant page
- `frontend/src/app/reports/page.tsx` — query-based report generation page
- `frontend/src/app/composer/*` — policy drafting workspace

### Existing backend capabilities to build on
- `src/api/search.py` — hybrid search
- `src/api/bills.py` — bill detail/list
- `src/api/compare.py` — similar bills + compare
- `src/api/analysis.py` — summarize, classify, version diff, constitutional, patterns
- `src/api/chat.py` — conversational assistant
- `src/api/collections.py` — collection CRUD
- `src/api/reports.py` — report generation

### Constraints
- Do not invent a brand-new backend domain model for investigations in v1 unless the collections scaffold proves insufficient.
- Do not make composer/policy drafting the home-page product story for MVP.
- Do not remove advanced capabilities from the codebase; demote them in navigation/positioning instead.
- Prefer thin composition work over deep new infrastructure.

---

## MVP reshape outcome

When this plan is complete, the product should feel like this:

1. The homepage explains an investigation-first policy research workflow.
2. Primary navigation emphasizes:
   - Investigations
   - Search
   - Assistant (or Copilot)
   - optional secondary Research/Explore routes
3. Collections are renamed/reframed in the UI as Investigations.
4. Investigation detail becomes the main working surface.
5. The assistant can work against a specific investigation context by default.
6. Report generation becomes investigation-aware, not only freeform query-driven.
7. Composer remains accessible but is visually positioned as an advanced / downstream workflow.

---

## Implementation phases

1. Product language and navigation reshaping
2. Collections -> Investigations UI reframing
3. Investigation workspace page redesign
4. Collection-aware / investigation-aware output generation
5. Assistant + bill-detail workflow tightening
6. Demotion of non-MVP-primary surfaces
7. Verification and docs refresh

---

## Phase 1: Product language and navigation reshaping

### Task 1: Audit and document all primary user-facing product labels

**Objective:** Create an explicit inventory of the current top-level product language before changing it.

**Files:**
- Inspect: `frontend/src/app/page.tsx`
- Inspect: `frontend/src/components/site-header.tsx`
- Inspect: `frontend/src/app/collections/page.tsx`
- Inspect: `frontend/src/app/assistant/page.tsx`
- Inspect: `frontend/src/app/reports/page.tsx`
- Inspect: `frontend/src/app/composer/page.tsx`
- Create: `docs/plans/notes/2026-04-08-mvp-reshape-label-inventory.md`

**Step 1: Write a short label inventory note**
Include:
- current homepage headline/subheadline
- current nav items
- current labels for collections, assistant, reports, composer
- obvious drafting-first language that conflicts with the MVP spec

**Step 2: Verify completeness**
Run a quick grep for likely user-facing labels.

Run:
`python3 - <<'PY'
from pathlib import Path
for p in Path('frontend/src').rglob('*.tsx'):
    text = p.read_text()
    if any(s in text for s in ['Policy Drafting IDE', 'Collections', 'Composer', 'Research Assistant', 'Reports']):
        print(p)
PY`

Expected: list of key files containing current product-facing language.

**Step 3: Commit**
```bash
git add docs/plans/notes/2026-04-08-mvp-reshape-label-inventory.md
git commit -m "docs: inventory current MVP-facing product labels"
```

### Task 2: Rewrite homepage copy around investigations, not drafting

**Objective:** Make the homepage tell the MVP story from the product spec.

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Test: visual/manual verification in browser

**Step 1: Write the new copy block**
Replace the drafting-first positioning with investigation-first positioning.

Required changes:
- headline should emphasize research workspace / investigation workflow
- primary CTA should point to investigations, not composer
- secondary CTA should point to search/explore
- feature cards should prioritize:
  - investigation workspace
  - cross-jurisdiction comparison
  - grounded copilot
  - report/memo generation

**Step 2: Preserve implementation simplicity**
Do not redesign the entire homepage layout. Keep the existing component structure and swap copy/card order first.

**Step 3: Verify in dev server**
Run:
`cd frontend && npm run dev`

Then visually confirm:
- hero no longer leads with drafting
- CTA hierarchy matches MVP
- the page still renders cleanly

**Step 4: Commit**
```bash
git add frontend/src/app/page.tsx
git commit -m "feat: reposition homepage around investigation-first MVP"
```

### Task 3: Reshape top navigation to reflect MVP priorities

**Objective:** Make the global nav reflect the new MVP IA.

**Files:**
- Modify: `frontend/src/components/site-header.tsx`
- Optional modify: `frontend/src/app/layout.tsx` if footer branding also needs adjustment

**Step 1: Define target nav**
Recommended MVP-primary nav order:
- Investigations
- Search
- Assistant
- optional: Explore

Secondary / advanced routes should move to one of:
- a More menu
- lower priority nav position
- investigation-local entry points

At minimum, de-emphasize:
- Composer
- Reports
- Jurisdictions
- Legislators

**Step 2: Implement minimal nav change**
Do not build a full dropdown menu unless needed immediately. A simple reorder + relabel + reducing visible primary items is acceptable for v1.

**Step 3: Verify route highlighting still works**
Manually navigate to:
- `/collections`
- `/search`
- `/assistant`
- `/composer`
- `/reports`

Confirm active styling behaves sensibly.

**Step 4: Commit**
```bash
git add frontend/src/components/site-header.tsx frontend/src/app/layout.tsx
git commit -m "feat: align top navigation with MVP investigation workflow"
```

---

## Phase 2: Reframe collections as investigations

### Task 4: Rename collections UI labels to investigations in the frontend

**Objective:** Keep the backend object but change the user-facing concept.

**Files:**
- Modify: `frontend/src/app/collections/page.tsx`
- Modify: `frontend/src/app/collections/[id]/page.tsx`
- Modify: `frontend/src/components/save-to-collection.tsx`
- Inspect: `frontend/src/types/api.ts` (no rename needed unless UI helper types are desired)

**Step 1: Update list page copy**
Change:
- "Research Collections" -> "Investigations"
- helper text to describe an investigation as a working set for a policy question
- create form placeholder to encourage investigation naming
  - example: "Qualified immunity reform - 2026"

**Step 2: Update detail page copy**
Change wording from collection to investigation throughout.

Add small framing text near the top like:
- investigation question / topic
- working set guidance
- prompt to use assistant or compare bills from this set

**Step 3: Update add-to-collection affordances**
In `save-to-collection.tsx`, change modal/button text to investigation language while keeping API calls unchanged.

**Step 4: Verify there is no backend dependency on the frontend label**
Run typecheck/build if available.

Suggested commands:
```bash
cd frontend
npm run lint
npm run build
```

Expected: pass, or only known non-blocking issues unrelated to this change.

**Step 5: Commit**
```bash
git add frontend/src/app/collections/page.tsx frontend/src/app/collections/[id]/page.tsx frontend/src/components/save-to-collection.tsx
git commit -m "feat: reframe collections as investigations in UI"
```

### Task 5: Add investigation metadata framing without new backend schema

**Objective:** Make an investigation feel like a project, not a bare list of bills.

**Files:**
- Modify: `frontend/src/app/collections/[id]/page.tsx`

**Step 1: Add lightweight presentational sections**
Without changing the API model yet, add UI sections for:
- investigation summary / description
- working set count
- quick actions:
  - ask assistant about this investigation
  - compare bills from this investigation
  - generate memo from this investigation

Use existing collection description field as initial summary.

**Step 2: Improve empty and sparse states**
When investigation has 0 items:
- guide user back to search
When it has 1 item:
- suggest adding comparison candidates

**Step 3: Commit**
```bash
git add frontend/src/app/collections/[id]/page.tsx
git commit -m "feat: add investigation framing and quick actions"
```

---

## Phase 3: Turn investigation detail into the main working surface

### Task 6: Design a single investigation workspace layout using the existing collection detail page

**Objective:** Make `/collections/[id]` feel like the canonical MVP workspace.

**Files:**
- Modify: `frontend/src/app/collections/[id]/page.tsx`
- May create: `frontend/src/components/investigation-header.tsx`
- May create: `frontend/src/components/investigation-working-set.tsx`
- May create: `frontend/src/components/investigation-actions.tsx`

**Step 1: Refactor page into 3 logical zones**
Target layout:
- top: investigation header
- left/main: working set of bills with notes and actions
- right or secondary panel: quick actions / guidance

This does not need a fully responsive desktop IDE layout yet. A stacked layout is acceptable if the sections are clearly investigation-centric.

**Step 2: Add explicit quick actions per investigation**
Buttons/links should include:
- Ask Copilot
- Compare Bills
- Generate Memo
- Continue Search

These can route to existing surfaces with context query params initially.

**Step 3: Add per-item actions**
For each bill in the working set, add clear actions such as:
- Open bill
- Compare
- Remove

Optional later:
- pin as key precedent
- mark as outlier

**Step 4: Commit**
```bash
git add frontend/src/app/collections/[id]/page.tsx frontend/src/components/investigation-*.tsx
git commit -m "feat: reshape collection detail into investigation workspace"
```

### Task 7: Pass investigation context into downstream routes with query params

**Objective:** Let existing routes behave investigation-aware without building a new backend object model first.

**Files:**
- Modify: `frontend/src/app/collections/[id]/page.tsx`
- Modify: `frontend/src/app/compare/page.tsx`
- Modify: `frontend/src/app/reports/page.tsx`
- Modify: `frontend/src/app/assistant/page.tsx`
- Inspect/modify: `frontend/src/lib/api.ts` if helper utilities are useful

**Step 1: Define lightweight context convention**
Use URL params like:
- `?collection_id=123`
- or `?investigation_id=123` in UI while mapping to collection ID internally

**Step 2: Add these links from the investigation page**
- Ask Copilot -> `/assistant?collection_id=123`
- Generate Memo -> `/reports?collection_id=123`
- Compare -> `/compare?collection_id=123`
- Continue Search -> `/search?collection_id=123`

**Step 3: Make target pages read the param and alter copy/behavior**
Even before deep functionality changes, the pages should acknowledge active investigation context.

**Step 4: Commit**
```bash
git add frontend/src/app/collections/[id]/page.tsx frontend/src/app/assistant/page.tsx frontend/src/app/reports/page.tsx frontend/src/app/compare/page.tsx
 git commit -m "feat: thread investigation context through research routes"
```

---

## Phase 4: Make outputs investigation-aware

### Task 8: Add investigation-based report generation as the preferred reports workflow

**Objective:** Shift reports from freeform query tool toward investigation output tool.

**Files:**
- Modify: `frontend/src/app/reports/page.tsx`
- Inspect/possibly modify: `src/api/reports.py`
- May create backend endpoint later: `POST /collections/{id}/report` or reuse existing query path temporarily

**Step 1: Implement the thin UI version first**
If `collection_id` is present in the URL:
- change heading/copy to memo/report from current investigation
- load investigation bills
- either:
  - generate the report from the collection bill set if backend support is added, or
  - prefill a query/report scaffold while clearly labeling it as derived from the active working set

**Step 2: If needed, add backend support explicitly**
Preferred backend addition:
- `POST /collections/{collection_id}/report`

This endpoint should:
- load collection bills
- load full bill text
- call the existing harness report method
- return the same `ReportOutput` shape

**Step 3: Keep the original freeform query path available**
But visually demote it behind the investigation-first path.

**Step 4: Verify report generation works in both modes**
Manual checks:
- no collection context -> old query flow still works
- collection context -> investigation-aware report path works

**Step 5: Commit**
```bash
git add frontend/src/app/reports/page.tsx src/api/reports.py src/schemas/*.py
 git commit -m "feat: make reports investigation-aware"
```

### Task 9: Add a lightweight evidence/provenance section to report UI

**Objective:** Make research outputs feel grounded and trustworthy.

**Files:**
- Modify: `frontend/src/app/reports/page.tsx`
- Possibly modify backend response only if necessary for richer context

**Step 1: Add a minimal evidence-used display**
For investigation-aware reports, show:
- bill count analyzed
- jurisdictions covered
- maybe explicit bill links or identifiers used

Do not overengineer citations yet.

**Step 2: Ensure the report page links back to source bills**
A user should be able to jump from memo -> working set -> underlying bill detail.

**Step 3: Commit**
```bash
git add frontend/src/app/reports/page.tsx
git commit -m "feat: add lightweight provenance to report outputs"
```

---

## Phase 5: Tighten assistant and bill-detail workflows around investigations

### Task 10: Make assistant page investigation-aware by default

**Objective:** Turn the assistant from a generic chat page into an investigation copilot when context exists.

**Files:**
- Modify: `frontend/src/app/assistant/page.tsx`
- Modify: `frontend/src/components/chat-panel.tsx`
- Inspect: `frontend/src/lib/api.ts` and `frontend/src/lib/sse.ts`
- Inspect backend support in `src/api/chat.py`

**Step 1: Add investigation-aware copy**
When `collection_id` is present:
- heading should reference the active investigation
- intro copy should say the assistant is working over the current investigation / working set

**Step 2: If backend support does not exist, implement a thin first pass**
Minimum acceptable first pass:
- pre-load or summarize collection context into the prompt path
- or provide a visible list of working-set bills above the assistant

Preferred follow-up:
- add a dedicated collection-aware assistant flow on the backend if needed

**Step 3: Preserve existing generic assistant mode**
No collection context -> current assistant behavior remains.

**Step 4: Commit**
```bash
git add frontend/src/app/assistant/page.tsx frontend/src/components/chat-panel.tsx src/api/chat.py
 git commit -m "feat: make assistant collection-aware for investigations"
```

### Task 11: Add investigation-first actions on bill detail page

**Objective:** Make each bill detail page feel like a context node within an investigation.

**Files:**
- Modify: `frontend/src/app/bills/[id]/page.tsx`
- Possibly modify: `frontend/src/components/save-to-collection.tsx`

**Step 1: Add clearer investigation actions**
Near the header actions, support:
- Save to Investigation
- Compare with another bill
- Ask Copilot about this bill

If an investigation is active in URL context, the page should reflect that.

**Step 2: Improve contextual navigation**
When coming from an investigation, provide a back-link like:
- Back to Investigation

**Step 3: Commit**
```bash
git add frontend/src/app/bills/[id]/page.tsx frontend/src/components/save-to-collection.tsx
git commit -m "feat: add investigation-first actions to bill detail"
```

---

## Phase 6: Demote non-MVP-primary surfaces

### Task 12: Reposition composer as advanced or downstream workflow

**Objective:** Keep the feature, but remove it from the primary MVP story.

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/components/site-header.tsx`
- Inspect: any docs or demo copy that overstate composer as the primary product

**Step 1: Remove composer as the homepage primary CTA**
Search/explore + investigations should lead.

**Step 2: Move composer lower in nav priority**
It can live in:
- secondary nav position
- more menu
- advanced workflows section

**Step 3: Update composer page intro**
Position it as:
- downstream drafting workflow
- or advanced drafting environment built on top of the research substrate

**Step 4: Commit**
```bash
git add frontend/src/app/page.tsx frontend/src/components/site-header.tsx frontend/src/app/composer/page.tsx
git commit -m "feat: demote composer from primary MVP positioning"
```

### Task 13: Demote reports / jurisdictions / legislators from top-level story without removing utility

**Objective:** Keep these useful, but stop treating them as equal primary destinations.

**Files:**
- Modify: `frontend/src/components/site-header.tsx`
- Possibly add an Explore page later; for now, use reduced nav prominence

**Step 1: Decide secondary placement strategy**
Simple version for MVP:
- keep routes intact
- remove from primary nav
- link from search, investigation, and bill pages where relevant

**Step 2: Verify discoverability still exists**
A user should still be able to reach:
- legislators
- jurisdictions
- reports
but not see them as the main product story.

**Step 3: Commit**
```bash
git add frontend/src/components/site-header.tsx
git commit -m "feat: reduce prominence of non-core MVP routes"
```

---

## Phase 7: Verification and docs refresh

### Task 14: Update demo and scope docs to match the refined MVP story

**Objective:** Align internal docs with the investigation-first MVP.

**Files:**
- Modify: `docs/demo-walkthrough.md`
- Modify: `docs/scopes/2026-03-21-cursor-for-public-policy-scope.md`
- Modify: any stale docs that still frame the homepage product as drafting-first

**Step 1: Update demo walkthrough opening**
The first 2 minutes of the demo should lead with:
- investigation workspace
- search + compare + working set + copilot
and treat composer as downstream or advanced.

**Step 2: Update scope wording where needed**
Reflect the current product decision:
- research copilot first
- drafting second

**Step 3: Commit**
```bash
git add docs/demo-walkthrough.md docs/scopes/2026-03-21-cursor-for-public-policy-scope.md
git commit -m "docs: align demo and scope docs with investigation-first MVP"
```

### Task 15: Full verification pass

**Objective:** Confirm the reshaped app actually behaves like the intended MVP.

**Files:**
- No code changes unless bugs are found

**Step 1: Run frontend checks**
```bash
cd /home/marcu/work/legislative-research-tool/frontend
npm run lint
npm run build
```
Expected: success, or only pre-existing unrelated issues.

**Step 2: Manual user-flow verification**
Verify this exact flow:
1. Land on homepage
2. Click into Investigations / Collections
3. Open an investigation
4. Go to search and add bills
5. Return to investigation
6. Launch assistant from investigation
7. Launch compare from investigation
8. Generate report from investigation
9. Open a bill and return to investigation context

Expected: no broken links, confusing labels, or dead-end transitions.

**Step 3: Record any follow-up gaps**
Create a short follow-up note if needed:
- `docs/plans/notes/2026-04-08-mvp-reshape-followups.md`

**Step 4: Commit if follow-up note added**
```bash
git add docs/plans/notes/2026-04-08-mvp-reshape-followups.md
git commit -m "docs: capture MVP reshape follow-up gaps"
```

---

## Recommended execution order

Implement in this exact order:
1. homepage and nav language
2. collections -> investigations relabeling
3. investigation detail page reshaping
4. investigation context threading into assistant/reports/compare
5. report generation from investigation context
6. bill detail actions and back-links
7. demotion of composer and secondary routes
8. docs refresh
9. full verification

This order maximizes visible product coherence early while minimizing backend churn.

---

## YAGNI / DRY guardrails

Do not do these during MVP reshape unless blocked:
- build a new `investigations` database table up front
- redesign the entire frontend with a brand-new component system
- build full multi-pane IDE chrome if a stacked layout will prove the workflow
- add deep citation/annotation infrastructure before the working-set loop is solid
- migrate every advanced capability into the investigation surface immediately

Prefer:
- relabeling and reframing current strong primitives
- thin composition over new abstraction
- investigation-aware routing/context over backend reinvention

---

## Definition of done

This plan is done when:
- the homepage and nav clearly describe an investigation-first research product
- collections are effectively investigations in the UI
- `/collections/[id]` feels like the main working surface
- assistant and reports become investigation-aware
- bill detail pages support investigation-centric navigation/actions
- drafting/composer remains available but no longer defines the MVP story
- docs/demo materials match the refined product direction

---

## Handoff note

Plan complete and ready for execution. The implementation should reuse the current codebase aggressively and avoid inventing a new platform model before the investigation workflow is validated.
