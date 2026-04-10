# Daily Automation Setup

Created jobs
- `legis-daily-smoke` — 9:00 AM weekdays
- `legis-daily-triage` — 9:10 AM weekdays
- `legis-daily-fix-pass` — 9:20 AM weekdays

Delivery
- All jobs deliver summaries back to the current origin chat.

Artifacts
- Jobs write reports into `docs/qa/`.

Guardrails
- The fix pass is intentionally conservative.
- It attempts at most one small low-risk fix.
- It avoids migrations, dependency changes, major refactors, and provider/auth-stack work.
