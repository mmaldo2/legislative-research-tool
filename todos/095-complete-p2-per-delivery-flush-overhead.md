---
status: complete
priority: p2
issue_id: "095"
tags: [code-review, performance]
dependencies: []
---

# Per-Delivery Flush Overhead with Unused "attempting" Status

## Problem

"attempting" status set + session.flush() per delivery = 50 extra DB round-trips per batch. No code queries for "attempting" status, and no recovery mechanism for stuck "attempting" deliveries exists.

## Files

- src/services/webhook_dispatcher.py:154-155

## Solution

Remove the intermediate "attempting" status and per-delivery flush. Instead use SELECT ... FOR UPDATE SKIP LOCKED on the initial poll query to prevent concurrent worker conflicts.
