# MVP Stage Follow-Ups 2

Date: 2026-04-09

## What landed in this pass
- Search now carries active investigation context and shows a banner when launched from an investigation.
- Search results preserve collection context when navigating into bill detail.
- Bill detail pages now preserve investigation continuity and show a back-link to the active investigation.
- Similar bills now support direct compare actions that preserve investigation context.
- Compare results now include clearer continuity back into the active investigation and selected bills.
- Top navigation now has a more explicit primary/secondary split via a `More` menu.
- Investigation pages now suggest next actions based on working-set size.

## Remaining polish gaps

1. Assistant backend context
- Still frontend prompt-prefix based rather than backend collection-aware.

2. Search triage UX
- Search remains one-bill-at-a-time for building an investigation. Bulk triage would make the workflow much faster.

3. Investigation layout sophistication
- The workspace is coherent now, but not yet fully IDE-like. A richer two-pane/sidecar investigation layout could be a future improvement.

4. Report provenance granularity
- Evidence links are clickable now, but reports still do not connect individual memo sections back to specific source bills.

5. Advanced route discoverability
- The `More` menu is a solid MVP improvement, but a more intentional advanced-workflows IA could still improve long-term usability.

## Verification notes
- Frontend `npm run build` passed.
- Frontend `npm run lint` still reports only the same pre-existing warnings in composer/chat-panel.
