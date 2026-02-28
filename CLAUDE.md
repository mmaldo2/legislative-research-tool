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
- `src/api/` — FastAPI route handlers
- `src/ingestion/` — Data pipeline (GovInfo, Open States, LegiScan)
- `src/llm/` — LLM harness (Anthropic SDK, structured outputs, prompt versioning)
- `src/search/` — Hybrid search (BM25 + pgvector + reranker)
- `tests/` — pytest tests mirroring src/ structure

## Key Patterns
- Each ingester normalizes upstream data to canonical schema via `normalizer.py`
- LLM results cached by content hash — don't re-process unchanged bills
- AI analyses stored in append-only `ai_analyses` table with prompt versioning
- Every API response includes provenance metadata (source, last_updated, ai model)

## Environment Variables
- `DATABASE_URL` — PostgreSQL connection (default: postgresql+asyncpg://legis:legis_dev@localhost:5432/legis)
- `ANTHROPIC_API_KEY` — Claude API key
- `VOYAGE_API_KEY` — Voyage AI API key for embeddings
- `CONGRESS_API_KEY` — Congress.gov API key (optional, supplements GovInfo)
- `OPENSTATES_API_KEY` — Open States v3 API key
