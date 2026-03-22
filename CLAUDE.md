# Legislative Research Tool

## Project Overview
AI-native legislative research platform. Python backend (FastAPI), PostgreSQL + pgvector, Anthropic SDK for LLM analysis.

## Commands
- **Run API**: `uvicorn src.api.app:app --reload`
- **Run tests**: `pytest`
- **Lint**: `ruff check src/ tests/`
- **Format**: `ruff format src/ tests/`
- **DB migrate**: `alembic upgrade head`
- **DB new migration**: `alembic revision --autogenerate -m "description"`
- **CLI**: `python -m src.cli <command>`
- **MCP server**: `python -m src.mcp.server` (stdio transport for IDE/Claude Desktop)
- **MCP dev/inspect**: `mcp dev src/mcp/server.py` (opens MCP Inspector UI)

## Conventions
- Python 3.12+, type hints everywhere
- Async SQLAlchemy with asyncpg
- Pydantic models shared between API schemas and LLM structured outputs
- All database operations use async session context managers
- Tests use pytest + pytest-asyncio
- Commit messages: conventional commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`)
- Ruff for linting and formatting (line length 100)

## Architecture
- `src/models/` — SQLAlchemy ORM models
- `src/schemas/` — Pydantic request/response models (shared with LLM outputs)
- `src/api/` — FastAPI route handlers (flat modules, not nested routers/)
- `src/ingestion/` — Data pipeline (GovInfo, Open States, LegiScan)
- `src/llm/` — LLM harness (Anthropic SDK, structured outputs, prompt versioning)
- `src/search/` — Hybrid search (BM25 + pgvector + reranker)
- `scripts/` — CLI utilities (historical backfill, etc.)
- `autoresearch/` — Self-contained ML experimentation sandbox (see below)
- `src/mcp/` — MCP server exposing research tools (search_bills, get_bill_detail, etc.)
- `tests/` — pytest tests mirroring src/ structure

## Key Patterns
- Each ingester normalizes upstream data to canonical schema via `normalizer.py`
- LLM results cached by content hash — don't re-process unchanged bills
- AI analyses stored in append-only `ai_analyses` table with prompt versioning
- Every API response includes provenance metadata (source, last_updated, ai model)
- Bulk upserts via `pg_insert().on_conflict_do_nothing/update()` — no SELECT-before-INSERT
- Bill models have schema-drift comments warning about `autoresearch/prepare.py` hardcoded SQL
- MCP server reuses existing tool handlers from `src/api/chat.py` — each tool call gets its own DB session
- When no `ANTHROPIC_API_KEY` is set, chat endpoints use Agent SDK + MCP for tool-use loops

## Autoresearch Module
Self-contained R&D sandbox for bill outcome prediction. Uses raw psycopg2 (not the ORM) to read from the same Postgres database. Does NOT import from `src/`.

- `autoresearch/prepare.py` — Fixed evaluation harness (DO NOT MODIFY during experiments)
- `autoresearch/train.py` — Model code the AI agent iterates on
- `autoresearch/program.md` — Research director instructions for autonomous agent
- `autoresearch/requirements.txt` — Isolated ML dependencies (install separately)
- `autoresearch/experiments/` — Timestamped experiment logs with metrics.json

**Running experiments**: `pip install -r autoresearch/requirements.txt && cd autoresearch && python train.py`

## Historical Backfill
- `scripts/backfill_historical.py` — Orchestrates GovInfo ingestion for Congress 110-118
- `--enrich-only` — Only fetch per-bill details (actions, cosponsors) for already-ingested bills
- `--no-enrich` — Only fetch bill list metadata, skip detail enrichment
- Resumable: re-running skips already-ingested/enriched bills
- Rate limit: Congress.gov API at 5,000 req/hr, handled by `_rate_limited_get()` with 429 backoff

## Environment Variables
- `DATABASE_URL` — PostgreSQL connection (default: postgresql+asyncpg://legis:legis_dev@localhost:5432/legis)
- `ANTHROPIC_API_KEY` — Claude API key
- `VOYAGE_API_KEY` — Voyage AI API key for embeddings
- `CONGRESS_API_KEY` — Congress.gov API key (required for historical backfill and enrichment)
- `OPENSTATES_API_KEY` — Open States v3 API key
