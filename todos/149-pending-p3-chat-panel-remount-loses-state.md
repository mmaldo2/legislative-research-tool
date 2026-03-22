---
status: resolved
priority: p3
issue_id: 149
tags: [quality, code-review]
---

# ChatPanel Remount on Collapsible Toggle Loses Conversation State

## Problem Statement

The ChatPanel component unmounts when the "Research Assistant" collapsible section is
toggled closed, destroying all in-memory conversation state. Reopening the panel starts
a fresh conversation, losing context the user built up.

## Findings

- The collapsible uses conditional rendering (`{isOpen && <ChatPanel />}`), which
  unmounts the component on close.
- Conversation messages and pending tool calls are stored in ChatPanel's local state.
- No state persistence mechanism (parent lift or context) preserves state across
  mount/unmount cycles.

## Technical Details

**Files:**
- `frontend/src/app/composer/[id]/page.tsx` — collapsible toggle logic
- `frontend/src/components/chat-panel.tsx` — conversation state management

**Recommended fix (pick one):**
1. **CSS toggle**: Replace conditional rendering with `style={{ display: isOpen ? 'block' : 'none' }}` so the component stays mounted but hidden.
2. **Lift state**: Move conversation state to the parent page component and pass it as
   props, so it survives ChatPanel unmount/remount.

Option 1 is simpler and preserves all internal state including scroll position.

## Acceptance Criteria

- [ ] Closing and reopening the Research Assistant panel preserves conversation history.
- [ ] Scroll position is maintained across toggle cycles.
- [ ] No additional network requests are fired on reopen.
