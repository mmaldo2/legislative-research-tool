# Codex local dev workflow

Status
- `AGENTIC_PROVIDER` now defaults to `codex-local` in local/dev settings.
- Assistant, compare, collection memo generation, and generic report generation use the local Codex bridge by default unless `AGENTIC_PROVIDER` is overridden.

## Backend startup

From the repo root in WSL:

```bash
PREWARM_BM25=false /home/marcu/work/legislative-research-tool/.venv/bin/uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

Notes
- This uses the default `AGENTIC_PROVIDER=codex-local` path.
- If you need to disable the Codex bridge and fall back to the old provider path, set:

```bash
AGENTIC_PROVIDER='' PREWARM_BM25=false /home/marcu/work/legislative-research-tool/.venv/bin/uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

## Frontend startup

From `frontend/` in WSL against the Windows repo:

```bash
npm run dev:webpack
```

Why this script exists
- Turbopack was failing on the Windows-mounted repo under WSL with `.next` write errors.
- `--webpack` has been the safer dev path in this environment.

## What is now on Codex delegated auth by default

When `AGENTIC_PROVIDER=codex-local`:
- `/api/v1/chat`
- `/api/v1/chat/stream`
- `/api/v1/collections/{id}/report`
- `/api/v1/reports/generate`
- `/api/v1/analyze/compare`

These flows reuse the locally authenticated Windows Codex runtime instead of requiring an OpenAI API key in the backend path.

## Known caveats

- `VOYAGE_API_KEY` is still unset in this environment, so semantic search quality is degraded even though search continues to work.
- Prediction remains separate from the Codex path; its failures are related to missing ML artifacts, not Codex auth/runtime.
- The Codex bridge depends on a working Windows-side Codex login state.
