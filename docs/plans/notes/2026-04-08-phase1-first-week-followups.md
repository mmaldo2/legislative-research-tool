# Phase 1 First-Week Follow-Ups

Date: 2026-04-08

## What changed in Phase 1
- Homepage is now investigation-first instead of drafting-first
- Primary navigation now leads with Investigations, Search, and Assistant
- Collections are relabeled as Investigations in the main frontend surfaces
- The collection detail page now reads like an investigation workspace and includes quick actions
- Save controls now use investigation language

## Remaining gaps for the next slice

1. Assistant is still mostly global
- The investigation page links into `/assistant?collection_id=...`, but the assistant page does not yet fully load and work against the active investigation by default.

2. Reports are still mostly query-driven
- The investigation page links into `/reports?collection_id=...`, but the reports page does not yet generate outputs from the active working set.

3. Investigation detail still shows limited bill metadata
- The page is more project-like now, but each item is still relatively sparse. A later pass should enrich investigation items with title/jurisdiction/status if that can be done cheaply.

4. Compare flow is not investigation-native yet
- Compare is still a separate surface. The next slice should make it easier to launch bill-to-bill comparison directly from the active investigation.

5. Advanced routes are only partially demoted
- Composer, Reports, Jurisdictions, and Legislators are lower-priority now, but the app does not yet have a true secondary navigation or more-menu structure.

## Verification notes
- `npm run build` passed successfully.
- `npm run lint` passed with pre-existing warnings only:
  - unused variable in `composer/[id]/page.tsx`
  - missing React hook dependency in `composer/[id]/page.tsx`
  - unused import/type in `components/chat-panel.tsx`

These warnings were not introduced by the Phase 1 reshape work.
