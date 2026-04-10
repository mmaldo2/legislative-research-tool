# Phase 2 Follow-Ups

Date: 2026-04-08

## What landed in Phase 2
- Assistant page now detects `collection_id` query context and frames itself as working inside an active investigation.
- Investigation context is passed into the assistant prompt as a lightweight working-set summary.
- Reports page now supports investigation-aware memo generation from `/collections/{id}/report`.
- Investigation-aware reports display a lightweight `Evidence Used` section based on the active working set.

## Remaining gaps

1. Assistant grounding is still thin
- The current approach prepends investigation context to the message. This is a useful first step, but a stronger long-term version would make the backend chat flow explicitly collection-aware rather than relying on prompt prefixing.

2. Investigation detail still has sparse bill metadata
- Working-set items still mainly display bill IDs plus notes. A stronger workspace would surface title, jurisdiction, and status directly in the list.

3. Compare flow is still separate
- There is still no clean, investigation-native compare launcher that lets a user pick two bills from the active working set.

4. Reports from investigations do not yet expose direct bill links in the generated output view
- The `Evidence Used` section lists bill IDs and notes, but users should eventually be able to click directly into underlying bills.

5. Nav demotion is still lightweight
- The app still exposes several advanced routes in top navigation. A later pass should introduce a real secondary navigation or overflow pattern.

## Verification notes
- `npm run build` passed successfully.
- `npm run lint` passed with the same pre-existing warnings from composer/chat-panel areas and no new blocking issues.
