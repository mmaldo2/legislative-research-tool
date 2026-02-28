---
title: "AI-Native Legislative Research & Analysis Tool — MVP Implementation Plan"
type: feat
status: active
date: 2026-02-28
scope: federal + 50-state coverage
team: solo + Claude Code
upstream_roadmap: AI_Legislative_Research_Tool_Roadmap.md
---

# AI-Native Legislative Research & Analysis Tool — MVP Implementation Plan

## Overview

Build an AI-native legislative research platform that ingests federal and state legislation from freely available public sources, enriches it with LLM-powered analysis (summaries, topic classification, cross-jurisdiction similarity), and exposes it through a clean REST API and researcher-friendly web UI. The tool targets policy researchers and advocacy organizations who need analytical depth — not just bill tracking — at a price point they can actually afford.

This plan is designed for a **solo developer using Claude Code** as the primary development accelerator. It prioritizes getting a working end-to-end system fast, then iterating on quality and coverage.

## Problem Statement

Existing legislative intelligence tools (Quorum, Plural/Open States, LegiScan) are optimized for government relations professionals doing bill tracking and alerts. Policy research organizations need fundamentally different capabilities:

- **Semantic search** across jurisdictions ("show me every bill that would expand qualified immunity")
- **Cross-state pattern detection** (model legislation identification, policy diffusion tracking)
- **Research-grade summaries** with citations to specific bill text
- **Version comparison** (what changed between introduced and engrossed?)

These organizations typically can't afford $10K-50K+/year enterprise pricing. The gap between "free bill tracker" and "enterprise GR platform" is the opportunity.

## Data Source Strategy (Updated February 2026)

### Critical Updates from Research

| Source | Status | Role in Our System |
|--------|--------|--------------------|
| **GovInfo.gov** (bulk + API + MCP) | Active, expanding | **Primary federal source** — bill text, status, CFR, statutes |
| **GovInfo MCP Server** (Jan 2026) | Public preview | **AI-native federal integration** — direct LLM-to-data pipeline |
| **Congress.gov API** | Unstable (Aug 2025 outage) | **Secondary federal source** — supplements GovInfo, not depended on |
| **Open States / Plural v3 API** | Active, free tier | **Primary state source** — all 50 states + DC + PR |
| **Open States Bulk Downloads** | Active | **State bulk ingestion** — monthly PG dumps, JSON/CSV per session |
| **LegiScan Weekly Datasets** | Active, free account | **Validation/gap-fill** — weekly ZIPs, uniform schema, CC BY 4.0 |
| **unitedstates/congress-legislators** | Active (Jan 2026) | **Federal member data** — public domain, comprehensive |
| ~~ProPublica Congress API~~ | **DEAD (July 2024)** | ~~Removed from plan~~ |

### Recommended Composite Pipeline

```
Layer 1 — Federal backbone:
  GovInfo bulk data (bill text XML, bill status, summaries)
  + GovInfo MCP server (real-time AI queries)
  + Congress.gov API (supplementary, with fallback if unstable)
  + unitedstates/congress-legislators (member biographical data)

Layer 2 — State backbone:
  Open States bulk downloads (monthly PG dumps for initial load)
  + Open States v3 API (incremental updates between dumps)

Layer 3 — Validation:
  LegiScan weekly datasets (cross-reference, gap detection)

Layer 4 — Context (Phase 2+):
  CRS reports, Federal Register, CourtListener
```

## Technical Approach

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Phase 2)                       │
│  Next.js + TailwindCSS + shadcn/ui                          │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────┐       │
│  │ Search &   │ │ Bill       │ │ Research           │       │
│  │ Discovery  │ │ Viewer     │ │ Assistant (chat)   │       │
│  └────────────┘ └────────────┘ └────────────────────┘       │
└─────────────────────┬───────────────────────────────────────┘
                      │ REST API (OpenAPI 3.1)
┌─────────────────────┴───────────────────────────────────────┐
│                     API Layer (Phase 1)                      │
│  FastAPI (Python 3.12+)                                     │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────┐       │
│  │ Bill       │ │ Search     │ │ AI Analysis        │       │
│  │ Endpoints  │ │ Engine     │ │ Endpoints          │       │
│  └────────────┘ └────────────┘ └────────────────────┘       │
│                                                              │
│  Pydantic models shared across API schemas + LLM outputs    │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────┐
│                     LLM Harness                              │
│  Anthropic SDK (native structured outputs, batch API)       │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────┐       │
│  │ Summarize  │ │ Classify   │ │ Compare / Assess   │       │
│  │ (Sonnet)   │ │ (Haiku)    │ │ (Sonnet)           │       │
│  └────────────┘ └────────────┘ └────────────────────┘       │
│  Prompt caching │ Cost tracking │ Content-hash dedup        │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────┐
│                     Data Layer                               │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐   │
│  │ PostgreSQL   │ │ bm25s        │ │ pgvector           │   │
│  │ + pgvector   │ │ (keyword     │ │ (Voyage-law-2      │   │
│  │ (canonical   │ │  search)     │ │  embeddings)       │   │
│  │  entities)   │ │              │ │                    │   │
│  └──────────────┘ └──────────────┘ └────────────────────┘   │
│                                                              │
│  Hybrid search: BM25 + vector + reranker (RRF fusion)       │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────┐
│                  Ingestion Pipeline                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │ GovInfo  │ │ Open     │ │ LegiScan │ │ unitedstates/  │  │
│  │ Bulk +   │ │ States   │ │ Weekly   │ │ congress-      │  │
│  │ MCP      │ │ Bulk +   │ │ Datasets │ │ legislators    │  │
│  │          │ │ API      │ │          │ │                │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
│                                                              │
│  Orchestration: APScheduler (lightweight, solo-dev friendly) │
│  Raw artifact storage: local filesystem → S3 (later)         │
└──────────────────────────────────────────────────────────────┘
```

### Key Technology Choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Language** | Python 3.12+ | LLM ecosystem, data processing, FastAPI |
| **API framework** | FastAPI | Async-native, Pydantic-native, auto OpenAPI docs |
| **Database** | PostgreSQL 16 + pgvector + pgvectorscale | Single DB for relational + vector. Open States dumps restore directly. |
| **LLM SDK** | Raw Anthropic SDK | Native structured outputs (GA), prompt caching, batch API. No framework overhead. |
| **Default model** | Claude Sonnet 4.6 ($3/$15/MTok) | Best cost/quality for extraction and summarization |
| **Classification model** | Claude Haiku 4.5 ($1/$5/MTok) | Fast, cheap — topic classification, triage |
| **Embeddings** | Voyage-law-2 | Best legal/legislative retrieval on MTEB. 16K context handles long bills. |
| **Keyword search** | bm25s (Python) | Near-Elasticsearch speed, zero infrastructure, pure Python |
| **Search fusion** | Reciprocal Rank Fusion (RRF) | Combines BM25 + vector rankings without score normalization issues |
| **Structured outputs** | `output_config.format` + Pydantic | Constrained decoding — model literally cannot produce invalid JSON |
| **Task scheduling** | APScheduler | Lightweight, in-process. No Redis/Celery overhead for solo dev. |
| **Evaluation** | DeepEval + custom legal metrics | pytest-native, CI/CD ready |
| **Containerization** | Docker Compose | PostgreSQL + app in one `docker compose up` |

### Database Schema

```sql
-- Core entities --

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgvectorscale;

-- Jurisdictions (federal + 50 states + DC + territories)
CREATE TABLE jurisdictions (
    id TEXT PRIMARY KEY,             -- 'us', 'us-ca', 'us-tx'
    name TEXT NOT NULL,
    classification TEXT NOT NULL,    -- 'country', 'state', 'territory'
    abbreviation TEXT,
    fips_code TEXT
);

-- Legislative sessions
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    jurisdiction_id TEXT NOT NULL REFERENCES jurisdictions(id),
    name TEXT NOT NULL,
    identifier TEXT NOT NULL,
    classification TEXT,             -- 'primary', 'special'
    start_date DATE,
    end_date DATE
);

-- Bills (central entity)
CREATE TABLE bills (
    id TEXT PRIMARY KEY,             -- internal stable ID
    jurisdiction_id TEXT NOT NULL REFERENCES jurisdictions(id),
    session_id TEXT NOT NULL REFERENCES sessions(id),
    identifier TEXT NOT NULL,        -- 'HB 1234', 'S. 567'
    title TEXT NOT NULL,
    classification TEXT[],           -- ['bill'], ['resolution']
    subject TEXT[],                  -- official subject tags
    status TEXT,                     -- normalized: introduced, passed_lower, passed_upper, enacted, vetoed, failed
    status_date DATE,

    -- Source cross-references (stable IDs from each upstream)
    openstates_id TEXT,
    legiscan_id INTEGER,
    congress_bill_id TEXT,           -- e.g. 'hr1234-119'
    govinfo_package_id TEXT,

    -- Provenance
    source_urls JSONB DEFAULT '[]',
    last_ingested_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (jurisdiction_id, session_id, identifier)
);

-- Bill text versions
CREATE TABLE bill_texts (
    id TEXT PRIMARY KEY,
    bill_id TEXT NOT NULL REFERENCES bills(id),
    version_name TEXT NOT NULL,      -- 'Introduced', 'Engrossed', 'Enrolled'
    version_date DATE,
    content_text TEXT,               -- plain text extraction
    content_html TEXT,
    content_xml TEXT,                -- USLM XML for federal
    source_url TEXT,
    word_count INTEGER,
    content_hash TEXT,               -- SHA-256 for dedup/change detection

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bill actions / history
CREATE TABLE bill_actions (
    id SERIAL PRIMARY KEY,
    bill_id TEXT NOT NULL REFERENCES bills(id),
    action_date DATE NOT NULL,
    description TEXT NOT NULL,
    classification TEXT[],           -- ['introduction'], ['passage'], ['executive-signature']
    chamber TEXT,                    -- 'upper', 'lower'
    action_order INTEGER
);

-- People (legislators)
CREATE TABLE people (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sort_name TEXT,
    party TEXT,
    current_jurisdiction_id TEXT REFERENCES jurisdictions(id),
    current_chamber TEXT,
    current_district TEXT,
    image_url TEXT,

    -- Cross-source IDs
    openstates_id TEXT,
    bioguide_id TEXT,
    legiscan_id INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sponsorships
CREATE TABLE sponsorships (
    id SERIAL PRIMARY KEY,
    bill_id TEXT NOT NULL REFERENCES bills(id),
    person_id TEXT NOT NULL REFERENCES people(id),
    classification TEXT NOT NULL,    -- 'primary', 'cosponsor'

    UNIQUE (bill_id, person_id, classification)
);

-- Vote events
CREATE TABLE vote_events (
    id TEXT PRIMARY KEY,
    bill_id TEXT NOT NULL REFERENCES bills(id),
    vote_date DATE,
    chamber TEXT,
    motion_text TEXT,
    result TEXT,                     -- 'pass', 'fail'
    yes_count INTEGER,
    no_count INTEGER,
    other_count INTEGER
);

-- Individual vote records
CREATE TABLE vote_records (
    id SERIAL PRIMARY KEY,
    vote_event_id TEXT NOT NULL REFERENCES vote_events(id),
    person_id TEXT NOT NULL REFERENCES people(id),
    option TEXT NOT NULL,            -- 'yes', 'no', 'not voting', 'excused'

    UNIQUE (vote_event_id, person_id)
);

-- AI enrichment layer --

-- AI analysis results (append-only, versioned)
CREATE TABLE ai_analyses (
    id SERIAL PRIMARY KEY,
    bill_id TEXT NOT NULL REFERENCES bills(id),
    analysis_type TEXT NOT NULL,     -- 'summary', 'topics', 'impact', 'constitutional_flags', 'diff'
    result JSONB NOT NULL,           -- structured output from LLM
    model_used TEXT NOT NULL,        -- 'claude-sonnet-4-6'
    prompt_version TEXT NOT NULL,    -- 'summarize-v3'
    content_hash TEXT NOT NULL,      -- hash of input text — skip if unchanged
    tokens_input INTEGER,
    tokens_output INTEGER,
    cost_usd NUMERIC(10, 6),
    confidence NUMERIC(3, 2),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (bill_id, analysis_type, prompt_version, content_hash)
);

-- Bill embeddings (pgvector)
CREATE TABLE bill_embeddings (
    id SERIAL PRIMARY KEY,
    bill_id TEXT NOT NULL REFERENCES bills(id),
    text_id TEXT REFERENCES bill_texts(id), -- which text version was embedded
    embedding vector(1024),          -- Voyage-law-2 dimension
    model_version TEXT NOT NULL,
    content_hash TEXT NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Cross-jurisdictional similarity (computed offline)
CREATE TABLE bill_similarities (
    bill_id_a TEXT NOT NULL REFERENCES bills(id),
    bill_id_b TEXT NOT NULL REFERENCES bills(id),
    similarity_score FLOAT NOT NULL,
    similarity_type TEXT NOT NULL,   -- 'semantic', 'text_overlap'
    model_version TEXT,
    computed_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (bill_id_a, bill_id_b, similarity_type),
    CHECK (bill_id_a < bill_id_b)   -- canonical ordering, no duplicates
);

-- Ingestion tracking (observability)
CREATE TABLE ingestion_runs (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,            -- 'govinfo', 'openstates', 'legiscan'
    run_type TEXT NOT NULL,          -- 'full', 'incremental'
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT DEFAULT 'running',   -- 'running', 'completed', 'failed'
    bills_created INTEGER DEFAULT 0,
    bills_updated INTEGER DEFAULT 0,
    errors JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}'
);

-- Indexes --

CREATE INDEX idx_bills_jurisdiction ON bills(jurisdiction_id);
CREATE INDEX idx_bills_session ON bills(session_id);
CREATE INDEX idx_bills_status ON bills(status);
CREATE INDEX idx_bills_identifier ON bills(identifier);
CREATE INDEX idx_bill_texts_bill ON bill_texts(bill_id);
CREATE INDEX idx_bill_actions_bill ON bill_actions(bill_id);
CREATE INDEX idx_sponsorships_bill ON sponsorships(bill_id);
CREATE INDEX idx_sponsorships_person ON sponsorships(person_id);
CREATE INDEX idx_vote_events_bill ON vote_events(bill_id);
CREATE INDEX idx_ai_analyses_bill ON ai_analyses(bill_id);
CREATE INDEX idx_ai_analyses_type ON ai_analyses(analysis_type);
CREATE INDEX idx_bill_embeddings_bill ON bill_embeddings(bill_id);

-- Vector similarity index (IVFFlat for moderate scale, switch to HNSW at >1M rows)
CREATE INDEX idx_bill_embeddings_vector ON bill_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### API Surface

The API replaces and improves upon LegiScan's surface area:

```
Base: /api/v1

# Core data endpoints
GET  /jurisdictions                           # List all jurisdictions
GET  /jurisdictions/{id}                      # Jurisdiction detail + session list
GET  /sessions                                # List sessions (filter by jurisdiction)
GET  /bills                                   # List/filter bills
     ?jurisdiction=us-ca
     &session=2025
     &status=enacted
     &topic=education
     &sponsor=person-123
     &q=keyword search
GET  /bills/{id}                              # Full bill detail + AI summary
GET  /bills/{id}/texts                        # All text versions
GET  /bills/{id}/texts/{version_id}           # Specific text version
GET  /bills/{id}/actions                      # Action history
GET  /bills/{id}/votes                        # Vote events
GET  /bills/{id}/sponsors                     # Sponsors + cosponsors
GET  /bills/{id}/similar                      # Cross-jurisdiction similar bills
GET  /bills/{id}/analysis                     # All AI analyses for this bill
GET  /people                                  # List/filter legislators
GET  /people/{id}                             # Legislator detail + bills
GET  /people/{id}/votes                       # Voting record

# Search (hybrid: keyword + semantic)
GET  /search/bills?q=...                      # Hybrid search
     &jurisdiction=...
     &session=...
     &mode=keyword|semantic|hybrid            # default: hybrid

# AI analysis endpoints
POST /analyze/summarize                       # Generate bill summary
     { "bill_id": "..." }
POST /analyze/compare                         # Compare two bills or versions
     { "bill_id_a": "...", "bill_id_b": "..." }
POST /analyze/ask                             # Research assistant Q&A
     { "question": "...", "context": { "jurisdiction": "...", "topic": "..." } }

# Data health
GET  /status                                  # API health + ingestion status
GET  /ingestion/runs                          # Recent ingestion history
```

Every response includes provenance metadata:

```json
{
  "data": { ... },
  "meta": {
    "sources": ["govinfo", "openstates"],
    "last_updated": "2026-02-28T12:00:00Z",
    "ai_enriched": true,
    "ai_model": "claude-sonnet-4-6",
    "ai_prompt_version": "summarize-v3"
  }
}
```

### Project File Structure

```
legislative-research-tool/
├── docker-compose.yml              # PostgreSQL + app
├── Dockerfile
├── pyproject.toml                  # uv/pip project config
├── alembic.ini                     # DB migrations config
├── CLAUDE.md                       # Claude Code project instructions
│
├── src/
│   ├── __init__.py
│   ├── config.py                   # Settings via pydantic-settings
│   ├── database.py                 # SQLAlchemy async engine + session
│   │
│   ├── models/                     # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── jurisdiction.py
│   │   ├── session.py
│   │   ├── bill.py
│   │   ├── bill_text.py
│   │   ├── bill_action.py
│   │   ├── person.py
│   │   ├── sponsorship.py
│   │   ├── vote.py
│   │   ├── ai_analysis.py
│   │   └── ingestion_run.py
│   │
│   ├── schemas/                    # Pydantic models (API + LLM shared)
│   │   ├── __init__.py
│   │   ├── bill.py                 # BillResponse, BillListResponse
│   │   ├── search.py               # SearchRequest, SearchResult
│   │   ├── analysis.py             # SummaryOutput, TopicOutput, CompareOutput
│   │   └── common.py               # Pagination, MetaResponse
│   │
│   ├── api/                        # FastAPI routes
│   │   ├── __init__.py
│   │   ├── app.py                  # FastAPI app factory
│   │   ├── bills.py
│   │   ├── people.py
│   │   ├── search.py
│   │   ├── analysis.py
│   │   └── status.py
│   │
│   ├── ingestion/                  # Data pipeline
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseIngester interface
│   │   ├── govinfo.py              # GovInfo bulk + API fetcher
│   │   ├── openstates.py           # Open States bulk + API ingester
│   │   ├── legiscan.py             # LegiScan weekly dataset ingester
│   │   ├── congress_legislators.py # unitedstates/congress-legislators
│   │   ├── normalizer.py           # Normalize upstream formats → canonical schema
│   │   └── scheduler.py            # APScheduler job definitions
│   │
│   ├── llm/                        # LLM harness
│   │   ├── __init__.py
│   │   ├── harness.py              # Core LLMHarness class
│   │   ├── prompts/                # Versioned prompt templates
│   │   │   ├── summarize_v1.py
│   │   │   ├── classify_v1.py
│   │   │   ├── compare_v1.py
│   │   │   └── assess_v1.py
│   │   ├── cost_tracker.py         # Token + cost accounting
│   │   └── cache.py                # Content-hash based result cache
│   │
│   ├── search/                     # Hybrid search engine
│   │   ├── __init__.py
│   │   ├── engine.py               # Hybrid search orchestrator
│   │   ├── bm25.py                 # BM25 keyword index (bm25s)
│   │   ├── vector.py               # pgvector semantic search
│   │   ├── embedder.py             # Voyage-law-2 embedding pipeline
│   │   └── reranker.py             # Cross-encoder reranking
│   │
│   └── cli.py                      # CLI commands (ingest, analyze, search)
│
├── migrations/                     # Alembic migration scripts
│   └── versions/
│
├── tests/
│   ├── conftest.py
│   ├── test_ingestion/
│   ├── test_llm/
│   ├── test_search/
│   ├── test_api/
│   └── eval/                       # LLM evaluation suite
│       ├── golden_set.json         # Manually annotated bill summaries
│       └── test_eval_quality.py    # DeepEval test cases
│
├── data/                           # Local data storage (gitignored)
│   ├── raw/                        # Upstream artifacts as-received
│   │   ├── govinfo/
│   │   ├── openstates/
│   │   └── legiscan/
│   └── exports/
│
└── docs/
    ├── plans/                      # This file lives here
    └── API.md                      # Generated from OpenAPI spec
```

### LLM Harness Design

The harness uses the Anthropic SDK's native structured outputs (GA as of 2026) — no tool_use workaround needed:

```python
# src/llm/harness.py — Core design

from anthropic import Anthropic
from pydantic import BaseModel
import hashlib

class BillSummary(BaseModel):
    """Structured output for bill summarization."""
    plain_english_summary: str
    key_provisions: list[str]
    affected_populations: list[str]
    changes_to_existing_law: list[str]
    fiscal_implications: str | None
    effective_date: str | None
    confidence: float  # 0.0-1.0

class LLMHarness:
    def __init__(self, client: Anthropic):
        self.client = client
        self.model_map = {
            "summarize": "claude-sonnet-4-6",
            "classify": "claude-haiku-4-5",
            "compare": "claude-sonnet-4-6",
            "assess": "claude-sonnet-4-6",
        }

    def content_hash(self, text: str, prompt_version: str) -> str:
        return hashlib.sha256(f"{prompt_version}:{text}".encode()).hexdigest()

    async def summarize(self, bill_text: str, bill_id: str) -> BillSummary:
        # Check cache by content_hash first
        # If cached and prompt version unchanged, return cached result

        response = self.client.messages.parse(
            model=self.model_map["summarize"],
            max_tokens=2048,
            system="You are a legislative analyst...",  # cached via prompt caching
            messages=[{"role": "user", "content": f"Summarize this bill:\n\n{bill_text}"}],
            output_format=BillSummary,
        )

        return response.parsed  # Fully typed Pydantic object
```

### Cost Estimates

At full national coverage (~175,000 bills/year):

| Operation | Model | Tokens | Rate (Batch) | Annual Cost |
|-----------|-------|--------|--------------|-------------|
| Summarization | Sonnet 4.6 | ~875M in, ~350M out | $1.50/$7.50 per MTok | ~$3,937 |
| Classification | Haiku 4.5 | ~875M in, ~50M out | $0.50/$2.50 per MTok | ~$562 |
| Embeddings | Voyage-law-2 | ~875M tokens | ~$0.12/MTok | ~$105 |
| Similarity compute | Sonnet 4.6 | ~100M in, ~50M out | $1.50/$7.50 per MTok | ~$525 |
| **Total LLM/year** | | | | **~$5,129** |

With prompt caching on system prompts (90% savings on cached reads), actual costs will be 20-30% lower. Very manageable for a solo project or small org.

## Implementation Phases

### Phase 0: Foundation (Target: 1 week)

**Goal**: Database running, first bills ingested, LLM harness producing summaries.

#### Tasks

- [x] `pyproject.toml` — Initialize Python project with uv. Dependencies: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `anthropic`, `pydantic`, `pydantic-settings`, `alembic`, `httpx`
- [x] `docker-compose.yml` — PostgreSQL 16 with pgvector extension
- [x] `CLAUDE.md` — Project conventions for Claude Code (Python style, testing patterns, commit format)
- [x] `src/config.py` — Environment-based settings (DB URL, API keys, model configs)
- [x] `src/database.py` — SQLAlchemy async engine + session factory
- [x] `src/models/` — All ORM models matching the schema above
- [ ] `migrations/` — Alembic initial migration from models (requires running DB)
- [x] `src/ingestion/govinfo.py` — Fetch current Congress bills from GovInfo bulk data (BILLSTATUS XML → parse → insert). Start with 119th Congress.
- [x] `src/ingestion/openstates.py` — Fetch state bills via Open States v3 API for pilot states (CA, TX, NY). Parse into canonical schema.
- [x] `src/llm/harness.py` — Core harness with `summarize()` using native structured outputs
- [x] `src/llm/prompts/summarize_v1.py` — First summarization prompt, calibrated for policy researchers
- [x] `src/cli.py` — CLI commands: `ingest federal`, `ingest states`, `analyze bill <id>`
- [x] `tests/test_llm/test_harness.py` — Test structured output parsing, content-hash caching
- [ ] **Manual evaluation**: Run summarization on 25 federal + 25 state bills, read outputs, iterate on prompt

#### Acceptance Criteria

- `docker compose up` starts PostgreSQL with pgvector
- `python -m src.cli ingest federal` fetches and stores 119th Congress bills
- `python -m src.cli ingest states` loads CA, TX, NY from Open States dump
- `python -m src.cli analyze bill <id>` produces a structured BillSummary
- Summary quality is "would a policy researcher find this useful?" — yes for 80%+ of test cases

---

### Phase 1: API + Search (Target: 2-3 weeks after Phase 0)

**Goal**: Working REST API with hybrid search. A developer (or the frontend later) can query bills, search semantically, and get AI summaries.

#### Tasks

- [x] `src/api/app.py` — FastAPI app with CORS, error handling, OpenAPI metadata
- [x] `src/api/bills.py` — Bill CRUD endpoints with filtering
- [x] `src/api/people.py` — Legislator endpoints
- [x] `src/api/search.py` — Hybrid search endpoint
- [x] `src/api/analysis.py` — AI analysis endpoints (summarize, compare)
- [x] `src/api/status.py` — Health check + ingestion status
- [x] `src/search/embedder.py` — Voyage-law-2 embedding pipeline (batch embed all bill texts)
- [x] `src/search/bm25.py` — BM25 index built from bill texts + titles
- [x] `src/search/vector.py` — pgvector similarity search
- [x] `src/search/engine.py` — Hybrid search with RRF fusion
- [x] `src/ingestion/congress_legislators.py` — Import unitedstates/congress-legislators YAML
- [x] `src/ingestion/scheduler.py` — APScheduler: daily federal check, weekly state refresh
- [x] `src/llm/prompts/classify_v1.py` — Topic classification prompt (Haiku)
- [x] `src/llm/cost_tracker.py` — Track tokens/costs per operation
- [x] Expand state coverage: ingest all 50 states from Open States bulk
- [x] `tests/test_api/` — API endpoint tests
- [x] `tests/test_search/` — Search relevance tests

#### Acceptance Criteria

- `GET /api/v1/bills?jurisdiction=us-ca&q=housing` returns relevant CA housing bills
- `GET /api/v1/search/bills?q=expand qualified immunity&mode=hybrid` returns relevant results across jurisdictions
- `GET /api/v1/bills/{id}` includes AI summary in response
- `POST /api/v1/analyze/summarize` generates summary on-demand for un-analyzed bills
- OpenAPI docs at `/docs` are complete and usable
- All 50 states + federal bills are in the database

---

### Phase 2: Frontend + Research Assistant (Target: 3-4 weeks after Phase 1)

**Goal**: Researcher-facing web UI with conversational assistant. Demoable to a policy org.

#### Tasks

- [ ] Next.js app with TailwindCSS + shadcn/ui
- [ ] Search page: keyword + semantic search with jurisdiction/session/topic facets
- [ ] Bill detail page: summary, full text viewer, version history, sponsors, vote record
- [ ] Cross-jurisdiction comparison view: side-by-side similar bills
- [ ] Legislator profile page: voting record, sponsored bills
- [ ] Jurisdiction dashboard: session overview, bill counts, trending topics
- [ ] Research assistant (chat): Claude-powered Q&A over the database via tool_use
- [ ] Research collections: save + annotate sets of bills
- [ ] Export: CSV download of search results, PDF bill briefs

#### Acceptance Criteria

- A policy researcher can search "data privacy bills 2025" and get relevant results across all 50 states
- Bill detail page shows AI summary + full text + version comparison
- Research assistant can answer "What states have introduced bills expanding qualified immunity this session?" with citations
- Collections let a researcher save and annotate a set of related bills

---

### Phase 3: Intelligence Layer (Target: ongoing after Phase 2)

**Goal**: Advanced analytical capabilities that create genuine competitive differentiation.

#### Tasks

- [ ] Cross-jurisdictional pattern detection (model legislation finder)
- [ ] Policy diffusion mapping (how ideas spread state to state over time)
- [ ] Version diff analysis (what changed between introduced and engrossed)
- [ ] Bill outcome prediction (using historical passage data)
- [ ] Constitutional flag analysis (First Amendment, preemption, commerce clause)
- [ ] Automated research reports (e.g., "2025 State of Free Speech Legislation")
- [ ] LegiScan weekly datasets as validation layer
- [ ] CRS report integration (federal policy context)
- [ ] GovInfo MCP server integration for real-time federal queries
- [ ] Evaluation suite: golden set of 100+ annotated bills, DeepEval quality regression

---

## Alternative Approaches Considered

### 1. Using LegiScan as sole data source

**Rejected.** Creates single-vendor dependency. Their free tier limits to one state + Congress. Bulk datasets are CC BY 4.0 which is fine, but Open States (public domain) + GovInfo (government works, no copyright) give cleaner licensing. Composite approach also enables higher data quality through cross-validation.

### 2. Django instead of FastAPI

**Rejected.** Django's ORM is synchronous — poor fit for LLM API calls that block for seconds. FastAPI's async-native design + Pydantic integration is a better match for this workload.

### 3. Elasticsearch/Meilisearch for search

**Deferred.** bm25s (pure Python) + pgvector gives us hybrid search with zero additional infrastructure. For a solo dev, managing fewer services matters. Can add Meilisearch later if bm25s becomes a bottleneck.

### 4. LangChain / LlamaIndex for LLM orchestration

**Rejected.** The raw Anthropic SDK with native structured outputs is simpler, has fewer abstractions to debug, and the document analysis tasks here are straightforward request-response patterns. If we later need complex agent orchestration, Pydantic AI is the preferred graduation path.

### 5. Separate vector database (Qdrant/Pinecone)

**Rejected.** pgvector keeps vectors in the same database as relational data — single transaction boundary, single backup, single deployment. At our scale (<5M vectors), pgvector with pgvectorscale is performant enough.

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Congress.gov API instability | High (proven) | Medium | GovInfo bulk data as primary; Congress.gov API as supplementary only |
| Open States data quality varies by state | Medium | Medium | LegiScan weekly datasets as validation/gap-fill layer |
| Voyage-law-2 API availability | Low | High | Fallback to OpenAI text-embedding-3-large; embeddings are re-computable |
| LLM costs exceed estimates | Low | Low | Batch API (50% off) + prompt caching (90% savings) + Haiku for cheap tasks |
| Schema changes from upstream sources | Medium | Medium | Connector interface pattern — each ingester normalizes to canonical schema |
| Solo dev burnout on 50-state coverage | Medium | High | Start with 3 pilot states, expand incrementally. Claude Code parallelizes grunt work. |

## Success Metrics

### Phase 0

- Database has >1,000 bills loaded (federal + 3 states)
- LLM summaries rated "useful" by developer for 80%+ of test cases

### Phase 1

- API serves all 50 states + federal with <500ms P95 latency for non-AI endpoints
- Hybrid search returns relevant results for 10 manually tested policy queries
- OpenAPI spec is complete and auto-generated

### Phase 2

- A non-technical policy researcher can use the UI to find and compare bills
- Research assistant answers cross-jurisdictional questions with citations
- Demo-ready for a policy organization

### Phase 3

- Model legislation detection identifies known instances (ALEC bills as ground truth)
- Evaluation suite catches quality regressions before deployment

## References

### Data Sources
- GovInfo Developer Hub: https://www.govinfo.gov/developers
- GovInfo MCP Server (Jan 2026): https://www.govinfo.gov/features/mcp-public-preview
- Open States API v3: https://docs.openstates.org/api-v3/
- Open States Bulk Data: https://open.pluralpolicy.com/data/
- Congress.gov API: https://api.congress.gov
- LegiScan Datasets: https://legiscan.com/datasets
- unitedstates/congress-legislators: https://github.com/unitedstates/congress-legislators

### Technical
- Anthropic Structured Outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Anthropic Batch API: https://platform.claude.com/docs/en/build-with-claude/batch-processing
- Anthropic Prompt Caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Voyage-law-2: https://blog.voyageai.com/2024/04/15/domain-specific-embeddings-and-retrieval-legal-edition-voyage-law-2/
- pgvector: https://github.com/pgvector/pgvector
- bm25s: https://github.com/xhluca/bm25s
- DeepEval: https://github.com/confident-ai/deepeval

### Existing Roadmap
- `AI_Legislative_Research_Tool_Roadmap.md` (in repo root) — original Claude Chat roadmap, used as foundation for this plan
