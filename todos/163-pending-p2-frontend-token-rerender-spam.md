---
status: pending
priority: p2
issue_id: 163
tags: [code-review, performance, frontend]
dependencies: []
---

# Frontend setStreamingText on Every Token Causes Excessive Re-renders

## Problem

ChatPanel calls `setStreamingText()` on every token event (~170 state updates per response). Each triggers a React re-render + `scrollIntoView({ behavior: "smooth" })` which forces layout reflow. Causes visible jank on lower-powered devices.

## Fix

Batch token updates with `requestAnimationFrame`. Accumulate tokens in a ref, flush to state at most once per frame.
