---
status: pending
priority: p1
issue_id: 152
tags: [code-review, architecture, streaming, performance]
dependencies: []
---

# Chat Streaming is Fake — No Latency Benefit Over Sync Endpoint

## Problem Statement

`stream_agentic_chat()` calls `client.messages.create()` (non-streaming) for every round including the final response, waits for the full completion, then chops the text into 12-character chunks to simulate streaming. Time-to-first-token is identical to the sync endpoint, defeating the purpose of SSE streaming.

## Findings

- `src/services/chat_service.py` lines 218-315: `stream_agentic_chat()` uses `client.messages.create()` (non-streaming)
- Lines 308-310: Final text emitted as fake 12-char chunks: `final_text[i : i + chunk_size]`
- The compose streaming in `harness.py` (`_run_analysis_stream`) DOES use true streaming via `client.messages.stream()` — inconsistency
- Comment at lines 303-307 acknowledges this is simulated: "emit it in chunks to simulate streaming (avoids a redundant API call)"
- The 12-character chunk size bears no relation to actual token boundaries, creating an unnatural flickery effect
- For complex agentic queries (up to 10 tool rounds + final synthesis), users see 15-60s of silence then a burst of fake tokens

## Proposed Solutions

### Option A: True streaming for the final turn (Recommended)
After the tool-use rounds complete, detect when the next response will be `end_turn` and use `client.messages.stream()` for that final call. Tool-use rounds remain non-streaming (tools need fully parsed input).
- Pros: Real token-by-token streaming, genuine latency improvement
- Cons: Slightly more complex loop logic, one additional API call on the final turn
- Effort: Medium

### Option B: Stream all rounds
Use `client.messages.stream()` for every round, streaming tool-use responses too. Parse tool calls from the stream.
- Pros: Maximum streaming fidelity
- Cons: Significantly more complex, must parse tool_use blocks from stream deltas
- Effort: Large
- Risk: Medium (stream parsing is tricky)

### Option C: Remove fake chunking, send full text in done event
Don't pretend to stream chat. Send tool_status events during tool use, then the full text in the done event.
- Pros: Honest UX — tool_status events still provide progress; simplest code
- Cons: No token-by-token streaming for chat (compose still has it)
- Effort: Small

## Acceptance Criteria

- [ ] Chat streaming endpoint delivers first visible token before the full LLM response is complete
- [ ] Or: if fake streaming is removed (Option C), the done event contains the full text and the frontend renders it immediately
- [ ] Tool-status events continue to show during agentic rounds regardless of approach chosen
