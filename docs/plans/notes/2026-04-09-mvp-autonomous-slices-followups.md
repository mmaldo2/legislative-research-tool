# MVP Autonomous Slices Follow-Ups

Date: 2026-04-09

## What landed in the autonomous slices
- Search now preserves investigation context and shows an active-investigation banner.
- Search result bill cards preserve `collection_id` when launched from an investigation.
- Bill detail pages now preserve investigation context and show a back-link to the active investigation.
- Similar bills inside bill detail now support direct compare actions that preserve investigation context.
- Compare results pages now show investigation continuity with back-links and selected-bill actions.
- Reports now show clickable evidence links back to bill detail pages with investigation context preserved.
- Navigation now has a clearer primary/secondary split via a `More` menu.
- Investigation pages now suggest stronger next steps and compare prompts.

## Remaining gaps before a fully polished MVP

1. Assistant context should become backend-native
- It currently uses a prompt prefix with collection context. This is useful, but the strongest product version would make chat explicitly collection-aware on the backend.

2. Search still lacks bulk add / triage ergonomics
- Search is investigation-aware now, but users still add bills one at a time. A stronger MVP might support quicker triage into investigations.

3. Investigation pages still do not feel fully IDE-like
- They are much stronger than before, but a future iteration could benefit from a two-pane layout or a more explicit active-context sidebar.

4. Reports still synthesize from the working set but do not cite sections back to specific bills
- The current clickable Evidence Used section is good, but more granular provenance would increase trust.

5. Compare results could suggest next actions directly
- e.g. add comparison notes back to investigation, ask assistant about these two bills, or generate memo section from this comparison.

## Verification notes
- Frontend `npm run build` passed.
- Frontend `npm run lint` still reports only pre-existing warnings in composer/chat-panel areas.
- Backend Python compile check for collection-related files passed.
