# Frontend development

## Recommended local dev command in this repo

From `frontend/`:

```bash
npm run dev:webpack
```

Why
- This Windows-mounted repo has hit Turbopack `.next` write failures under WSL.
- `dev:webpack` is the safer local path here.

## App/backend expectation

The frontend expects the backend at:
- `http://localhost:8000/api/v1`

For local backend work, the current default assistant/report/compare mode is:
- `AGENTIC_PROVIDER=codex-local`

That routes the main synthesis flows through the locally authenticated Codex bridge.
