# 2026-04-09 MVP Gap Audit

Context
- App audited live at `http://localhost:3000`
- Product benchmark: `docs/scopes/2026-04-08-cursor-for-public-policy-mvp-product-spec.md`
- Architectural lens: standalone app remains primary shell; investigations/working sets are the product center

## Executive verdict

Current state: promising scaffold, not yet MVP-ready.

What works
- The app now presents an investigation-first story in the homepage and collections UX.
- Search returns relevant results quickly.
- Creating an investigation works.
- Adding a bill to an investigation works from bill detail.
- Investigation-aware assistant and memo surfaces exist in the UI.
- Bill detail pages preserve enough structure to act as context nodes.

Why it is not yet MVP-ready
- The core synthesis loop breaks at the two highest-value moments: assistant and memo generation.
- Investigation continuity is still brittle and leaks context in key navigation paths.
- Comparison, which is a stated MVP core workflow, is not yet discoverable/usable enough.
- The home surface still behaves like a marketing landing page, not a re-entry point for active policy work.
- Evidence/provenance and output workflows are too thin to meet the spec’s trust bar.

## Audit criteria used

From the MVP spec, the most important checks were:
1. Can a user create/re-enter an investigation quickly?
2. Can a user search and build a working set with low friction?
3. Can a user inspect bills and move back into the investigation loop?
4. Can a user compare and analyze bills across jurisdictions?
5. Can a user ask follow-up questions over the active working set?
6. Can a user generate a usable research output grounded in the working set?
7. Does the product feel investigation-first rather than page-first?

## Findings

### 1. Investigation framing: improved, but re-entry is still weak
Status: warning

What worked
- Homepage headline and copy now match the investigation-first product story.
- Investigations page supports creating a working set around a policy question.
- Investigation detail page shows the right conceptual loop: search -> assistant -> memo.

Gaps
- The homepage still does not function as a practical re-entry dashboard.
- The spec calls for recent investigations / recently viewed bills / suggested follow-up activity, but the live home page is still mostly static marketing copy with two CTA links.
- Investigation detail page still feels like a transitional scaffold rather than the canonical workspace surface described in the spec.

Evidence
- Home page exposed only marketing copy plus `Open Investigations` / `Explore Search`.
- No recent investigations, outputs, or suggested next actions appeared on home even after creating a live investigation.

Impact
- Weakens the “return to active work quickly” part of the MVP promise.

### 2. Search quality is decent, but triage-to-working-set is still too click-heavy
Status: warning

What worked
- Search for `privacy` returned many relevant bills.
- Results loaded quickly and were plausibly relevant to the topic.

Gaps
- Search result cards are still mostly links, not working-set triage tools.
- No visible direct `Add to Investigation` or `Compare` actions on result cards.
- Search result bill links do not preserve investigation context in their hrefs.

Evidence
- DOM inspection of live search results showed bill links like:
  - `/bills/201c05b9faf66b61`
  - `/bills/e6e28def20073c4b`
  - `/bills/17b29c61d4a0ad0d`
- Those hrefs do not carry `collection_id` / investigation context.
- The spec explicitly calls for quick-add to working set from search and investigation-aware movement through the workflow.

Impact
- Building a 5-20 bill working set still requires too much bill-detail hopping.
- This weakens the core Cursor-like “triage into project context” loop.

### 3. Bill detail works as a context node, but trust is thin and continuity is brittle
Status: warning

What worked
- Bill detail pages expose the right tab structure: summary, text, actions, sponsors, similar, diff, etc.
- `Add to Investigation` worked from bill detail.
- `Back to Investigation` appears when a `collection_id` query param is present.

Gaps
- Trust is thin on many records because key panels are empty.
- Example privacy bill `S490` showed:
  - no AI summary available
  - `Text (0)`
  - `Actions (0)`
  - `Sponsors (0)`
  - `Similar`: `No similar bills found across jurisdictions.`
- The back-navigation / context continuity behavior is inconsistent.

Evidence
- Live bill detail for `S490` rendered empty counts on text/actions/sponsors and no AI summary.
- At one point, clicking `Back to Investigation` landed on `/collections/1` with `Collection not found.` even though the investigation existed and was visible on the investigations page.
- Direct navigation to a collection route also intermittently produced `Collection not found.` while clicking into the same investigation from the list worked.

Impact
- Undercuts the trust bar in the MVP spec.
- Makes the investigation workspace feel stateful in fragile ways rather than durable ways.

### 4. Working set scaffolding exists, but the workspace is still too thin
Status: warning

What worked
- Investigation creation works.
- Saved bill count updates correctly.
- Working set items render inside the investigation page.
- The page suggests next actions in a sensible way.

Gaps
- Workspace does not yet feel like the canonical Cursor-like environment from the spec.
- Left-rail / center-pane / right-pane mental model is not there yet.
- Analyst notes are not yet a visible, confident workflow.
- Generated outputs are not visible inside the investigation workspace.
- There is no strong “organize this set / compare these candidates / continue thread” experience yet.

Evidence
- Investigation page currently exposes a lightweight scaffold with links and saved bill cards, but no strong integrated outputs/evidence/copilot panes.
- Item notes appear only as `Click to add notes...`, not as a confident research-notes surface.

Impact
- The product still feels like linked pages around a collection rather than a durable research workspace.

### 5. Comparison is a core MVP promise, but the current comparison UX is not there yet
Status: broken

What worked
- A `/compare` route exists.
- Bill detail surfaces include a `Similar` tab and version diff tab.

Gaps
- Comparison is not discoverable enough from search or working set.
- `/compare` currently feels unfinished.
- The compare page only says `Select two bills to compare` and points users back to other flows, without an obvious in-page selection workflow.
- Search results and investigation workspace do not expose a clear compare-first CTA.

Evidence
- Live `/compare` page rendered only introductory copy, with no obvious bill picker or active comparison workflow.
- Search result cards showed no visible compare action.
- Investigation page showed no visible compare action even after a bill was saved.

Impact
- This fails one of the spec’s clearest core requirements: cross-jurisdiction comparison as a first-class workflow.

### 6. Assistant workflow is present in UI, but broken in practice
Status: broken

What worked
- Assistant page correctly recognized the active investigation and working set.
- The framing is good: the assistant is positioned as investigation-aware rather than generic.

Failure
- The first real question failed with a 503 configuration/runtime error.

Evidence
- Live error after asking: `What are the biggest differences across the bills in this investigation?`
- Response:
  - `Error: Stream request failed: 503 {"detail":"Agentic chat/workspace flows are not yet wired for OPENAI. Use LLM_PROVIDER=anthropic or LLM_PROVIDER=claude-sdk for those routes, or keep using OpenAI for the broader analysis/reporting system."}`

Impact
- This breaks one of the highest-value MVP actions.
- It also makes the product architecture leak into the user experience.

### 7. Memo/report generation workflow exists in UI, but broken in practice
Status: broken

What worked
- Investigation-aware report page exists.
- The framing is right: `Generate a memo from the active investigation and its current working set.`

Failure
- Clicking `Generate Memo from Investigation` failed immediately with runtime configuration error.

Evidence
- Live alert:
  - `LLM_PROVIDER=openai but OPENAI_API_KEY is not configured.`

Impact
- This breaks the final synthesis/output leg of the canonical MVP workflow.
- Search + save without memo generation does not fulfill the product promise.

### 8. Provenance and output trust are still too weak
Status: warning

What worked
- The app language emphasizes grounded research and investigation context.

Gaps
- There is not yet enough visible evidence trail in the core surfaces tested.
- Output creation is not yet succeeding, so the save/edit/export/provenance bar cannot be met.
- Bill detail often shows sparse or empty panels, which weakens trust even before synthesis.

Impact
- The app is directionally aligned with the trust requirements, but not yet operationally meeting them.

## Summary scorecard

- Investigation creation and persistence: partial pass
- Search and discovery: pass with important UX gaps
- Quick working-set construction: weak pass
- Bill detail as context node: partial pass
- Comparison workflow: fail
- Working-set-aware assistant: fail
- Memo/output generation: fail
- Re-entry / home / continuity: fail-to-warning range
- Trust / provenance: warning

## Recommended product conclusion

The app has crossed from generic legislative tooling toward the right MVP story, but it has not yet crossed the usability line for the canonical workflow:

Investigation -> Search -> Save working set -> Compare -> Ask copilot -> Generate memo

Today, the scaffold is visible, but the middle and end of that loop are still broken or too thin.

## Recommended implementation slices

### Slice 1 — Restore the broken synthesis loop
Goal
- Make assistant and memo generation usable from the investigation workflow.

Why first
- These are the highest-value broken steps in the MVP loop.
- Until these work, the product cannot satisfy its core promise.

Scope
- Fix runtime/provider wiring for assistant routes.
- Fix runtime/provider wiring for report generation routes.
- Ensure failures are surfaced as operator/setup issues during development, not confusing user-facing dead ends.
- Verify end-to-end from investigation context.

Success bar
- Ask investigation-aware assistant question successfully.
- Generate memo from active investigation successfully.

### Slice 2 — Make investigation continuity durable
Goal
- Eliminate context leaks when moving between investigation, search, and bill detail.

Why second
- The product promise depends on a durable project context.
- Current intermittent `Collection not found` / missing-context navigation undermines the whole workspace model.

Scope
- Preserve investigation context consistently in links and transitions.
- Ensure direct navigation and click navigation behave consistently.
- Make back-links and deep links reliable.
- Ensure search result links and bill detail routes preserve active investigation context where appropriate.

Success bar
- No investigation context drops during the canonical workflow.
- Direct route loads and click-through loads behave the same.

### Slice 3 — Upgrade search-to-working-set triage
Goal
- Let users build a working set quickly without opening every bill detail page.

Why third
- Search is already good enough to be useful; now it needs to become operationally efficient.

Scope
- Add direct `Add to Investigation` actions from search cards.
- Add clear `Compare` affordances where relevant.
- Surface why a result matched / useful snippet more clearly.
- Reinforce active investigation context visibly on search.

Success bar
- User can add multiple bills to a working set from search in a few clicks.
- Search clearly feels investigation-aware when entered from an investigation.

### Slice 4 — Make comparison a first-class workflow
Goal
- Turn compare from a buried/incomplete route into a visible MVP-strength action.

Why fourth
- Comparison is central to the product thesis and currently underpowered in UX.

Scope
- Add easy selection of two bills from working set and/or search.
- Make compare route usable without hidden setup knowledge.
- Improve transitions between comparison output and source bills.
- Keep version diff available, but do not let it substitute for cross-bill comparison UX.

Success bar
- User can compare two bills from the investigation workflow with minimal friction.

### Slice 5 — Strengthen the investigation workspace and re-entry surfaces
Goal
- Make the app feel like a durable research workspace rather than connected pages.

Why fifth
- Once the critical loop works, the biggest remaining gap is product feel and continuity.

Scope
- Upgrade home into a true re-entry dashboard.
- Surface recent investigations / recent bills / suggested next actions.
- Make investigation page a stronger workspace with visible notes, outputs, and activity.
- Improve output visibility inside the investigation, not just on a separate route.

Success bar
- Returning users can resume active work immediately.
- Investigation page feels like the canonical workspace, not just a collection detail view.

## Suggested uninterrupted execution order
1. Slice 1 — restore assistant + memo generation
2. Slice 2 — fix investigation continuity
3. Slice 3 — improve search triage into working set
4. Slice 4 — make comparison first-class
5. Slice 5 — improve home/workspace re-entry and polish
