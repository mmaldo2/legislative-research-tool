# Phase 3 Follow-Ups

Date: 2026-04-08

## What landed in Phase 3
- Investigation working-set items now expose richer bill metadata (identifier, title, jurisdiction, status) in the UI.
- Collection detail quick actions now include an investigation-native Compare Bills entry point.
- The compare flow now supports `collection_id` context and lets the user choose two bills from the active investigation.
- Backend collection detail responses now include bill metadata needed for richer investigation displays.

## Remaining gaps

1. Assistant should become backend collection-aware
- Prompt-prefix grounding works, but the stronger long-term version would let the backend explicitly load and reason over collection context.

2. Investigation working set could use richer affordances
- Good next upgrades would be pinning key bills, marking outliers, or surfacing the strongest two compare candidates automatically.

3. Compare results do not yet loop back deeply into the investigation
- The compare flow is now investigation-launched, but the comparison page itself could show stronger links back into the active investigation and the selected items.

4. Report evidence should become clickable
- The current Evidence Used section is useful, but bill links would make the memo output more navigable.

5. Navigation still lacks a true secondary surface
- The MVP is much clearer now, but advanced routes still deserve a cleaner secondary-navigation pattern instead of living in the main header forever.

## Verification notes
- `npm run build` passed successfully.
- `npm run lint` passed with the same pre-existing warnings in composer/chat-panel and no new blocking issues.
