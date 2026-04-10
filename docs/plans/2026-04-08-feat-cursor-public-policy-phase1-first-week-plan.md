# Cursor for Public Policy MVP — Phase 1 First-Week Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Ship the smallest high-leverage slice of the MVP reshape so the product immediately feels more investigation-first without requiring backend reinvention.

**Architecture:** This first-week slice only changes product framing and the main working surface. Reuse the existing homepage, nav, collections pages, collection-detail page, and save-to-collection control. Do not build a new investigation backend model yet. Collections remain the implementation scaffold; the UI starts calling them Investigations.

**Tech Stack:** Next.js App Router, TypeScript, shadcn/ui, existing collections/search/bill-detail frontend and API.

---

## Why this slice first

The full MVP reshape plan is broad. The highest-leverage first slice is the one that changes what the product feels like before changing deeper behavior.

This first week should accomplish four things:
1. homepage no longer says "policy drafting IDE"
2. nav no longer leads with drafting/platform surfaces
3. collections are reframed as investigations everywhere the user feels them
4. collection detail starts feeling like the main research workspace

If these four changes land well, the product story becomes legible immediately.

---

## Scope for the first week

### In scope
- homepage copy and CTA reshaping
- top navigation reshaping
- collections -> investigations frontend relabeling
- investigation framing on collection detail page
- quick actions from the investigation page
- save-to-collection control relabeled for investigations
- lightweight docs note capturing label decisions

### Out of scope
- backend model changes
- collection-aware assistant implementation
- investigation-aware report generation
- compare-page context threading
- bill-detail back-links into an active investigation
- composer demotion beyond nav/copy level
- new layout primitives or large UI redesign

---

## End-of-week outcome

By the end of this week:
- a new user lands on the homepage and understands the product as an investigation-driven research workbench
- the nav highlights Investigations, Search, and Assistant as primary surfaces
- the user can create an Investigation from the existing collections flow
- the investigation detail page feels like a real working set instead of a flat list
- the code changes are small, testable, and reversible

---

## Files in play

Primary files:
- `frontend/src/app/page.tsx`
- `frontend/src/components/site-header.tsx`
- `frontend/src/app/collections/page.tsx`
- `frontend/src/app/collections/[id]/page.tsx`
- `frontend/src/components/save-to-collection.tsx`
- `frontend/src/app/layout.tsx` (only if footer branding needs copy cleanup)

Optional supporting docs:
- `docs/plans/notes/2026-04-08-phase1-product-language-decisions.md`

---

## Week structure

- Day 1: language inventory + homepage repositioning
- Day 2: top navigation reshaping
- Day 3: collections list -> investigations list
- Day 4: collection detail -> investigation workspace framing
- Day 5: polish, verification, and doc capture

---

## Day 1: language inventory + homepage repositioning

### Task 1: Write a short language-decision note

**Objective:** Capture the product language choices for this first slice before editing UI.

**Files:**
- Create: `docs/plans/notes/2026-04-08-phase1-product-language-decisions.md`

**Step 1: Write a short note with the approved language**
Include:
- product headline direction: investigation-first
- `Collections` in backend/API remain `Collections`
- `Investigations` becomes the user-facing term in the frontend
- `Composer` remains an advanced/downstream drafting workflow, not the main headline
- `Assistant` may remain named Assistant for now; `Copilot` can be evaluated later

Suggested content skeleton:
```markdown
# Phase 1 Product Language Decisions

- Public product framing: investigation-driven policy research workspace
- User-facing label: Investigations
- Internal/backend object retained: Collections
- Composer remains available but is not the homepage story
- Primary workflow: Search -> save to investigation -> analyze -> synthesize
```

**Step 2: Commit**
```bash
git add docs/plans/notes/2026-04-08-phase1-product-language-decisions.md
git commit -m "docs: capture phase 1 product language decisions"
```

### Task 2: Reposition the homepage around investigation-first research

**Objective:** Change the first impression of the app with minimal layout churn.

**Files:**
- Modify: `frontend/src/app/page.tsx`

**Step 1: Write the failing acceptance checklist in a note or comment**
The homepage should satisfy:
- no drafting-first headline
- primary CTA points to investigations/working context
- secondary CTA points to search/explore
- feature cards prioritize investigation, comparison, copilot, research output

**Step 2: Update hero copy**
Change the current drafting-first hero.

Suggested replacement direction:
- headline: "The Policy Research Workspace"
- subhead: something like "Search across jurisdictions, build working sets of relevant bills, compare them, and generate research outputs in one environment."
- CTA 1: `Open Investigations` -> `/collections`
- CTA 2: `Explore Search` -> `/search`

**Step 3: Reorder feature cards**
Top four cards should emphasize:
- Investigations / working sets
- Cross-jurisdiction comparison
- Research Assistant / grounded copilot
- Research Reports / synthesis

Composer can remain present, but should not be card #1.

**Step 4: Run the dev server and verify visually**
Run:
```bash
cd /home/marcu/work/legislative-research-tool/frontend
npm run dev
```

Manual check:
- homepage copy reads as research-first
- CTA order is correct
- existing layout still looks clean on desktop

**Step 5: Commit**
```bash
git add frontend/src/app/page.tsx
git commit -m "feat: reposition homepage around investigation-first MVP"
```

---

## Day 2: top navigation reshaping

### Task 3: Reshape the primary nav to match MVP priorities

**Objective:** Make the nav reflect the core workflow without building new IA components.

**Files:**
- Modify: `frontend/src/components/site-header.tsx`
- Optional modify: `frontend/src/app/layout.tsx`

**Step 1: Define the minimal MVP nav**
Use this primary order for now:
- Investigations (`/collections`)
- Search (`/search`)
- Assistant (`/assistant`)

Secondary items can stay visible if necessary, but should be pushed later in the array:
- Reports
- Composer
- Jurisdictions
- Legislators

If you want an even tighter first pass, only show the first three in desktop nav and leave the rest in the mobile sheet or a future More menu. Prefer minimal churn this week.

**Step 2: Update labels and order**
In `site-header.tsx`:
- relabel Collections -> Investigations
- reorder nav items
- ensure active styling still works with `/collections`

**Step 3: Optional footer copy cleanup**
If needed, update `frontend/src/app/layout.tsx` footer from generic legislative tool language to something that does not fight the new positioning.

**Step 4: Verify route highlighting manually**
Manual route checks:
- `/collections`
- `/search`
- `/assistant`
- `/reports`
- `/composer`

Expected:
- active nav styling still works
- relabeled Investigations points to collections route

**Step 5: Commit**
```bash
git add frontend/src/components/site-header.tsx frontend/src/app/layout.tsx
git commit -m "feat: align navigation with investigation-first MVP"
```

---

## Day 3: collections list becomes investigations list

### Task 4: Reframe the collections index page as Investigations

**Objective:** Make the list page communicate project/workflow value instead of storage semantics.

**Files:**
- Modify: `frontend/src/app/collections/page.tsx`

**Step 1: Update page title and helper copy**
Change:
- `Research Collections` -> `Investigations`
- empty state to explain an investigation as a working set for a policy question

Suggested helper text:
- "Create an investigation to track the bills, notes, and research questions for a policy topic."

**Step 2: Update create form placeholder and button context**
Change the new collection placeholder to something investigation-like:
- `New investigation name...`

Suggested example names in placeholder/help text:
- `State data privacy enforcement - 2026`
- `Qualified immunity reform tracking`

**Step 3: Update card-level microcopy**
Keep the card structure simple, but make it feel like an active project surface.
If there is no description, consider a subtle fallback like:
- `No investigation summary yet`

**Step 4: Verify no API changes are needed**
Run:
```bash
cd /home/marcu/work/legislative-research-tool/frontend
npm run lint
```

Expected: no issues caused by text-only relabeling.

**Step 5: Commit**
```bash
git add frontend/src/app/collections/page.tsx
git commit -m "feat: reframe collections index as investigations"
```

### Task 5: Reframe save-to-collection actions as save-to-investigation

**Objective:** Make the action language match the product story at the point of use.

**Files:**
- Modify: `frontend/src/components/save-to-collection.tsx`

**Step 1: Update button text**
Change:
- `Save` -> `Save to Investigation` or `Add to Investigation`

For compactness, on small buttons you may use:
- `Add`
with menu text carrying the full label.

**Step 2: Update dropdown copy**
Change:
- `New collection...` -> `New investigation...`
- success feedback from `Saved` to something consistent if space permits

**Step 3: Keep implementation unchanged**
Do not rename component or backend API in this slice unless it materially improves readability. UI text change is enough.

**Step 4: Verify from bill detail page**
Open any bill detail page and confirm the control still works and reads naturally.

**Step 5: Commit**
```bash
git add frontend/src/components/save-to-collection.tsx
git commit -m "feat: relabel save controls around investigations"
```

---

## Day 4: collection detail becomes investigation workspace framing

### Task 6: Add investigation framing to the detail page header

**Objective:** Make `/collections/[id]` feel like a workspace, not just a bucket of bill IDs.

**Files:**
- Modify: `frontend/src/app/collections/[id]/page.tsx`

**Step 1: Update page labels**
Change visible language from collection to investigation throughout.

**Step 2: Add a short investigation framing block near the top**
Below the title/description, add a compact block with 1-2 lines such as:
- "Use this investigation to track a policy question, save the most relevant bills, and move into comparison or memo generation."

**Step 3: Add a visible item count / working set cue**
If the current page already implies count, make it more explicit:
- `Working set: N bills`

**Step 4: Improve the empty state**
If zero bills:
- suggest going to search
- present a clear CTA link/button to `/search`

**Step 5: Commit**
```bash
git add frontend/src/app/collections/[id]/page.tsx
git commit -m "feat: add investigation framing to detail page"
```

### Task 7: Add quick actions to the investigation page

**Objective:** Turn the detail page into a launch point for the core MVP workflow.

**Files:**
- Modify: `frontend/src/app/collections/[id]/page.tsx`

**Step 1: Add a compact quick-actions section**
Include links/buttons for:
- Continue Search -> `/search`
- Ask Assistant -> `/assistant?collection_id={id}`
- Generate Memo -> `/reports?collection_id={id}`

If compare needs at least two bills, either:
- omit it for now, or
- show `Compare Bills` only when `items.length >= 2`

**Step 2: Place the actions high enough to matter**
Put them near the header, not buried after the bill list.

**Step 3: Make the page feel like a project control surface**
Without redesigning the layout completely, ensure the hierarchy is:
- investigation title/summary
- quick actions
- working set
- notes/editing

**Step 4: Commit**
```bash
git add frontend/src/app/collections/[id]/page.tsx
git commit -m "feat: add investigation quick actions"
```

### Task 8: Improve working-set item presentation slightly

**Objective:** Make the working set more useful without major redesign.

**Files:**
- Modify: `frontend/src/app/collections/[id]/page.tsx`

**Step 1: Add explicit per-item actions**
For each item, ensure it is easy to:
- open the bill
- edit notes
- remove from investigation

If compare is easy to add later, leave a TODO note rather than overbuild now.

**Step 2: Improve bill identification**
If the detail page currently only shows bill ID, consider whether you can cheaply show richer bill metadata. If backend data is insufficient on this page right now, do not expand scope in this slice. Note the limitation for later.

**Step 3: Commit**
```bash
git add frontend/src/app/collections/[id]/page.tsx
git commit -m "feat: improve working-set presentation on investigation page"
```

---

## Day 5: verification and follow-up capture

### Task 9: Run first-slice verification

**Objective:** Confirm the first slice really changes the product feel.

**Files:**
- No code changes unless bugs found

**Step 1: Run frontend checks**
```bash
cd /home/marcu/work/legislative-research-tool/frontend
npm run lint
npm run build
```

Expected: success, or only unrelated pre-existing issues.

**Step 2: Manual workflow verification**
Verify this exact first-slice flow:
1. open homepage
2. understand the product as investigation-first
3. click Investigations
4. create a new investigation
5. open that investigation
6. use quick action to go to search or assistant
7. open a bill and use Add to Investigation
8. return to the investigation page and confirm the working-set concept still holds together

**Step 3: Record what still feels wrong/confusing**
Create:
- `docs/plans/notes/2026-04-08-phase1-first-week-followups.md`

Capture only real follow-up gaps, such as:
- assistant still feels too global
- report flow needs collection-aware backend support
- investigation detail still lacks richer bill metadata
- compare flow needs a smoother launch path from investigations

**Step 4: Commit follow-up note**
```bash
git add docs/plans/notes/2026-04-08-phase1-first-week-followups.md
git commit -m "docs: capture first-week MVP reshape follow-ups"
```

---

## Sequence summary

Implement in this order:
1. language decisions note
2. homepage repositioning
3. nav reshaping
4. collections list relabeling
5. save-to-investigation relabeling
6. investigation detail framing
7. quick actions on investigation page
8. working-set polish
9. verification + follow-up note

This is the smallest slice that changes the product story and the primary working surface without triggering backend redesign.

---

## Definition of done for Phase 1

Phase 1 is done when:
- the homepage reads investigation-first
- the nav leads with Investigations, Search, Assistant
- collections are called Investigations in the UI
- the collection detail page feels like an investigation workspace
- the user can move from an investigation toward search/assistant/report actions
- the product no longer appears drafting-first to a first-time visitor

---

## Handoff note

This first-week plan is intentionally narrow. It changes product perception and working-surface framing first. If it lands well, the next slice should make the assistant and reports genuinely investigation-aware, not just linked from the investigation page.
