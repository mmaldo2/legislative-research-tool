# AI-Native Legislative Research & Analysis Tool — Architecture & Roadmap

## Executive Summary

This document lays out a phased plan for building an AI-native legislative research and analysis platform covering both federal (Congress) and state (50-state) legislation. The primary user persona is **policy organization researchers** — the kind of analysts working at organizations like FIRE, Students for Liberty, Pelican Institute, or similar think tanks and advocacy groups that need deep, systematic legislative intelligence rather than surface-level bill tracking.

The core thesis is that existing tools (Plural/Quorum/USLege/FastDemocracy) are optimized for **government relations professionals** who need to track bills and get alerts. They are *not* built for researchers who need to ask questions like "show me every bill introduced across all 50 states in 2025 that would expand qualified immunity" or "how has the statutory language around data privacy evolved across jurisdictions since 2018?" That analytical gap is the opportunity.

The plan bypasses LegiScan's survey-gated API entirely by assembling a composite data pipeline from freely available sources, and positions the tool to eventually *surpass* LegiScan's data offering through LLM-powered enrichment.

---

## Part 1: The Data Landscape

### 1.1 Available Data Sources (No Approval Gates)

#### Federal Data

| Source | What It Provides | Access Method | Rate Limits | Notes |
|--------|-----------------|---------------|-------------|-------|
| **Congress.gov API** (Library of Congress) | Bills, amendments, actions, summaries, committees, sponsors, cosponsors, subjects, related bills, Congressional Record | REST API (JSON/XML) | 5,000 req/hr | Free API key, instant signup. Coverage from 93rd Congress (1973) forward for most data; bill text from 6th Congress (1799) |
| **GovInfo.gov** (GPO) | Full bill text (PDF, XML, HTML), committee reports, hearing transcripts, CFR, Federal Register | Bulk download + API | Generous | The authoritative source for bill *text*. XML versions are machine-parseable |
| **unitedstates/congress** (GitHub) | Pre-built Python scrapers for bill status, votes, bill text from GovInfo | Run locally | N/A | Maintained by GovTrack; outputs structured JSON. The gold standard open-source federal pipeline |
| **ProPublica Congress API** | Members, votes, bills, nominations, lobbying, statements | REST API (JSON) | Reasonable | Originated at NYT in 2009. Good for member-centric queries and vote comparisons. Bill data from 1995+ |
| **GovTrack.us** | Bills, votes, members, predictions, analysis | Bulk data + site | N/A | 20 years of maturity. Good secondary/validation source |
| **CRS Reports** (EveryCRSReport.com) | Congressional Research Service reports | Bulk download | N/A | Invaluable for policy context — nonpartisan expert analysis of issues |

#### State Data

| Source | What It Provides | Access Method | Rate Limits | Notes |
|--------|-----------------|---------------|-------------|-------|
| **Open States / Plural v3 API** | Bills, votes, sponsors, actions, committees, legislators for all 50 states + DC + PR | REST API (JSON) | Free tier available | The single best unified state data source. Monthly PostgreSQL bulk dumps also available |
| **Open States Bulk Downloads** | Full bill data, vote data, legislator data per session | JSON/CSV per session | N/A | Available at open.pluralpolicy.com/data/. Includes bill text in JSON downloads |
| **LegiScan Weekly Datasets** | Bill, vote, and legislator data snapshots | Bulk download (JSON/CSV) | Weekly refresh | Available at legiscan.com/datasets — these are *not* gated by the API survey. Current year + historical archives |
| **Individual State Legislature Sites** | Primary source data | Scraping required | Varies | Open States scrapers (openstates/openstates-scrapers on GitHub) already cover all 50 states and can be forked/extended |

#### Supplementary / Enrichment Sources

| Source | Value-Add |
|--------|-----------|
| **National Conference of State Legislatures (NCSL)** | Policy topic databases, session calendars, comparative state policy research |
| **Ballotpedia** | Election data, legislator bios, ballot measures — useful for connecting legislative activity to electoral context |
| **Follow The Money / OpenSecrets** | Campaign finance data linkable to legislators via common IDs |
| **Federal Register API** | Regulatory actions — critical for understanding the executive-side of policy implementation |
| **Court Listener / RECAP** | Judicial opinions — enables connecting legislation to judicial outcomes |

### 1.2 Data Source Strategy

The recommended approach is a **layered ingestion model**:

1. **Primary backbone**: Open States bulk dumps (state) + Congress.gov API / unitedstates/congress scrapers (federal) — these give you the structured metadata spine
2. **Text layer**: GovInfo.gov for federal bill text; Open States JSON downloads + direct state site scraping for state bill text
3. **Enrichment layer**: LegiScan weekly datasets as a validation/gap-filling source, cross-referenced against the primary backbone
4. **Context layer**: CRS reports, NCSL databases, and eventually court opinions and regulatory data

This composite approach means you're not dependent on any single vendor, and your data quality can actually exceed LegiScan because you're pulling from multiple authoritative sources and cross-validating.

---

## Part 2: Architecture

### 2.1 Recommended Tech Stack

Given the analytical/research focus and the need to handle large text corpora with LLM processing, the recommendation is **Python-dominant backend with a modern web frontend**:

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  Next.js (TypeScript) — researcher-facing UI                 │
│  React + TailwindCSS + shadcn/ui                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐          │
│  │ Search &  │  │ Bill     │  │ Analysis         │          │
│  │ Discovery │  │ Viewer   │  │ Dashboard        │          │
│  └──────────┘  └──────────┘  └──────────────────┘          │
└────────────────────────┬────────────────────────────────────┘
                         │ REST / GraphQL
┌────────────────────────┴────────────────────────────────────┐
│                     API Layer                                │
│  FastAPI (Python) — your own API that replaces LegiScan     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐          │
│  │ Bill      │  │ Search   │  │ AI Analysis      │          │
│  │ Endpoints │  │ Engine   │  │ Endpoints        │          │
│  └──────────┘  └──────────┘  └──────────────────┘          │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                    Data Layer                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ PostgreSQL   │  │ Meilisearch  │  │ pgvector /       │  │
│  │ (structured  │  │ or Typesense │  │ Qdrant           │  │
│  │  bill data)  │  │ (full-text)  │  │ (embeddings)     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                  Ingestion Pipeline                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ Congress  │  │ Open     │  │ LegiScan │  │ GovInfo    │ │
│  │ .gov API  │  │ States   │  │ Bulk     │  │ Bill Text  │ │
│  │ Fetcher   │  │ Ingester │  │ Ingester │  │ Fetcher    │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘ │
│                                                              │
│  Orchestration: Celery + Redis (or Prefect/Dagster)         │
│  Scheduling: cron / Celery Beat                              │
└──────────────────────────────────────────────────────────────┘
```

**Why this stack:**

- **PostgreSQL** is the natural choice because Open States already provides monthly pg dumps you can restore directly, and pgvector gives you semantic search without a separate vector DB
- **FastAPI** gives you automatic OpenAPI docs (your API *is* the LegiScan replacement), async support for concurrent scraping, and the Python ecosystem for NLP/LLM work
- **Meilisearch** (or Typesense) for full-text search is dramatically simpler than Elasticsearch for this use case, supports typo tolerance and faceted filtering, and is easy to self-host
- **Next.js frontend** because policy researchers expect a polished, fast UI and you'll want SSR for SEO if you ever open this up

### 2.2 Core Data Schema

The schema should be designed to be a **superset** of what LegiScan provides, with additional fields for LLM-generated enrichment:

```sql
-- Jurisdictions (federal + 50 states + DC + territories)
CREATE TABLE jurisdictions (
    id TEXT PRIMARY KEY,                    -- e.g., 'us', 'us-ca', 'us-tx'
    name TEXT NOT NULL,
    classification TEXT NOT NULL,           -- 'country', 'state', 'territory'
    fips_code TEXT,
    abbreviation TEXT
);

-- Legislative Sessions
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    jurisdiction_id TEXT REFERENCES jurisdictions(id),
    name TEXT NOT NULL,
    identifier TEXT NOT NULL,
    classification TEXT,                    -- 'primary', 'special'
    start_date DATE,
    end_date DATE
);

-- Bills (the central entity)
CREATE TABLE bills (
    id TEXT PRIMARY KEY,                    -- internal UUID or OCD ID
    jurisdiction_id TEXT REFERENCES jurisdictions(id),
    session_id TEXT REFERENCES sessions(id),
    identifier TEXT NOT NULL,               -- e.g., 'HB 1234', 'S. 567'
    title TEXT NOT NULL,
    classification TEXT[],                  -- ['bill'], ['resolution'], etc.
    subject TEXT[],                         -- state/LOC-assigned subjects
    status TEXT,                            -- normalized status enum
    status_date DATE,

    -- Source cross-references (critical for dedup & validation)
    openstates_id TEXT,
    legiscan_id INTEGER,
    congress_gov_id TEXT,

    -- LLM-enriched fields (what makes this AI-native)
    ai_summary TEXT,                        -- Claude-generated plain-english summary
    ai_topics TEXT[],                       -- ML-classified policy topics
    ai_impact_assessment JSONB,             -- structured impact analysis
    ai_similarity_cluster INTEGER,          -- cluster ID for similar bills
    ai_constitutional_flags TEXT[],         -- flagged constitutional issues
    embedding vector(1536),                 -- for semantic search

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    source_urls JSONB                       -- provenance tracking
);

-- Bill Texts (multiple versions per bill)
CREATE TABLE bill_texts (
    id TEXT PRIMARY KEY,
    bill_id TEXT REFERENCES bills(id),
    version_name TEXT,                      -- 'Introduced', 'Engrossed', 'Enrolled'
    date DATE,
    content_text TEXT,                       -- extracted plain text
    content_html TEXT,                       -- HTML version if available
    source_url TEXT,
    mime_type TEXT,
    ai_diff_summary TEXT                    -- LLM summary of changes vs prior version
);

-- Actions / History
CREATE TABLE bill_actions (
    id SERIAL PRIMARY KEY,
    bill_id TEXT REFERENCES bills(id),
    date DATE NOT NULL,
    description TEXT NOT NULL,
    classification TEXT[],                  -- normalized: ['introduction'], ['passage'], etc.
    chamber TEXT,                           -- 'upper', 'lower'
    order INTEGER
);

-- People (legislators)
CREATE TABLE people (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    party TEXT,
    current_jurisdiction_id TEXT REFERENCES jurisdictions(id),
    current_chamber TEXT,
    current_district TEXT,
    openstates_id TEXT,
    bioguide_id TEXT,                       -- federal
    legiscan_id INTEGER,
    followthemoney_id TEXT
);

-- Sponsorships
CREATE TABLE sponsorships (
    id SERIAL PRIMARY KEY,
    bill_id TEXT REFERENCES bills(id),
    person_id TEXT REFERENCES people(id),
    classification TEXT,                    -- 'primary', 'cosponsor'
    entity_type TEXT                        -- 'person', 'organization'
);

-- Votes
CREATE TABLE vote_events (
    id TEXT PRIMARY KEY,
    bill_id TEXT REFERENCES bills(id),
    date DATE,
    chamber TEXT,
    motion_text TEXT,
    result TEXT,                            -- 'pass', 'fail'
    yes_count INTEGER,
    no_count INTEGER,
    other_count INTEGER
);

CREATE TABLE vote_records (
    id SERIAL PRIMARY KEY,
    vote_event_id TEXT REFERENCES vote_events(id),
    person_id TEXT REFERENCES people(id),
    option TEXT                             -- 'yes', 'no', 'not voting', 'excused'
);

-- Cross-jurisdictional bill similarity (the killer feature)
CREATE TABLE bill_similarities (
    bill_id_a TEXT REFERENCES bills(id),
    bill_id_b TEXT REFERENCES bills(id),
    similarity_score FLOAT,
    similarity_type TEXT,                   -- 'text', 'semantic', 'structural'
    model_version TEXT,
    computed_at TIMESTAMPTZ,
    PRIMARY KEY (bill_id_a, bill_id_b)
);

-- Research collections (for power users)
CREATE TABLE collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    owner_id TEXT,                          -- user reference
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE collection_bills (
    collection_id UUID REFERENCES collections(id),
    bill_id TEXT REFERENCES bills(id),
    notes TEXT,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (collection_id, bill_id)
);
```

---

## Part 3: The LLM Layer — What Makes This "AI-Native"

This is the strategic differentiator. The AI layer isn't a chatbot bolted onto a bill tracker — it's a set of analytical capabilities that would take a human researcher days or weeks to perform manually.

### 3.1 MVP AI Capabilities (Phase 1)

**Bill Summarization Pipeline**
- Every bill text gets a structured summary: what the bill does, who it affects, what it changes in existing law, and key provisions
- Version-to-version diff summaries when bill text is amended
- Plain-English explanations calibrated for policy researchers (not lobbyist briefings, not public explainers)

**Semantic Search**
- Embed all bill texts and summaries using a model like `text-embedding-3-large`
- Enable queries like "bills that would restrict government surveillance of social media" across all jurisdictions
- This immediately surpasses LegiScan's keyword-based full-text search

**Topic Classification**
- Classify every bill into a policy taxonomy (start with NCSL's topic categories, refine over time)
- Enable faceted browsing: "show me all education bills in Southern states this session"

### 3.2 Advanced AI Capabilities (Phase 2-3)

**Cross-Jurisdictional Pattern Detection**
- "Model legislation" detection: identify when similar bill language appears across multiple states (ALEC-style coordination)
- Policy diffusion tracking: map how legislative ideas spread from state to state over time
- This is *extremely* valuable to policy researchers and is something no current tool does well

**Constitutional & Legal Flag Analysis**
- Flag potential First Amendment issues, preemption conflicts, dormant commerce clause problems
- Cross-reference against relevant court decisions (via CourtListener integration)
- This is the FIRE/civil-liberties use case: "show me every bill introduced this session that could implicate free speech on college campuses"

**Impact Assessment**
- Structured analysis: who are the stakeholders, what are the likely effects, what are the implementation challenges
- Comparative analysis: how does this bill compare to similar enacted legislation in other states

**Legislative Network Analysis**
- Sponsor/cosponsor network graphs
- Voting pattern clustering (ideal point estimation)
- Coalition detection across issue areas

### 3.3 LLM Harness Design (The MVP Core)

The LLM harness is the most important piece to get right early, because everything else builds on it. Here's the recommended architecture:

```python
# Core abstraction: every AI operation is a "Task" with structured I/O
from pydantic import BaseModel
from enum import Enum

class TaskType(str, Enum):
    SUMMARIZE = "summarize"
    CLASSIFY = "classify"
    COMPARE = "compare"
    EXTRACT = "extract"
    ASSESS = "assess"

class TaskInput(BaseModel):
    task_type: TaskType
    bill_id: str
    bill_text: str | None = None
    context: dict | None = None          # additional context (e.g., prior version for diff)
    parameters: dict | None = None        # task-specific params

class TaskOutput(BaseModel):
    task_type: TaskType
    bill_id: str
    result: dict                          # structured output, schema varies by task
    model_used: str
    tokens_used: int
    cost_estimate: float
    confidence: float | None = None
    created_at: datetime

class LLMHarness:
    """
    Core harness for all LLM operations. Handles:
    - Provider abstraction (Claude, GPT-4, local models)
    - Prompt management & versioning
    - Structured output parsing
    - Cost tracking
    - Retry/fallback logic
    - Caching (don't re-summarize unchanged bills)
    - Batch processing (Anthropic Batch API for bulk ops)
    """

    def __init__(self, config: HarnessConfig):
        self.providers = self._init_providers(config)
        self.prompt_registry = PromptRegistry()
        self.cache = ResultCache()
        self.cost_tracker = CostTracker()

    async def execute(self, task: TaskInput) -> TaskOutput:
        # Check cache first
        cached = await self.cache.get(task)
        if cached:
            return cached

        # Select provider & prompt
        provider = self._select_provider(task)
        prompt = self.prompt_registry.get(task.task_type)

        # Execute with retry logic
        result = await self._execute_with_retry(provider, prompt, task)

        # Parse structured output
        parsed = self._parse_output(task.task_type, result)

        # Track costs
        self.cost_tracker.record(result)

        # Cache result
        output = TaskOutput(...)
        await self.cache.set(task, output)

        return output

    async def execute_batch(self, tasks: list[TaskInput]) -> list[TaskOutput]:
        """Use Anthropic Batch API for bulk processing."""
        # Group by task type for consistent prompting
        # Submit batch, poll for completion
        # Parse and cache all results
        pass
```

**Key design principles for the harness:**

1. **Prompt versioning**: Every prompt template has a version. When you improve a prompt, you can re-run it against existing bills and compare quality. Store the prompt version alongside every output.

2. **Structured outputs**: Always use tool_use / function calling to get structured JSON from the LLM, never free-text parsing. Define Pydantic schemas for every task output.

3. **Cost awareness**: At 175,000 bills/year nationally, even cheap operations add up. Use Haiku for classification, Sonnet for summaries, Opus only for complex analysis. The Batch API (50% discount) is essential for bulk processing.

4. **Caching by content hash**: Hash the bill text + prompt version. If neither has changed, don't re-process. Bills that haven't been amended don't need re-summarization.

5. **Human-in-the-loop hooks**: For research orgs, the AI outputs should be treated as drafts. Build in annotation/correction flows from the start.

---

## Part 4: Phased Roadmap

### Phase 0: Foundation (Weeks 1-3)

**Goal**: Get data flowing into a database and prove the LLM harness works.

- [ ] Set up PostgreSQL + schema (use the schema above as starting point)
- [ ] Build Congress.gov API fetcher — start with current Congress bills
- [ ] Build GovInfo bill text fetcher (XML → plain text extraction)
- [ ] Restore an Open States monthly pg dump for state data
- [ ] Implement the core `LLMHarness` class with Claude as primary provider
- [ ] Build the summarization task with a well-crafted prompt
- [ ] Run summarization against 100 bills, manually evaluate quality
- [ ] Set up basic cost tracking

**Deliverable**: A database with federal + state bills, and LLM-generated summaries for a sample set. A working harness you can iterate on.

### Phase 1: MVP API (Weeks 4-8)

**Goal**: Build your own API that replicates LegiScan's core functionality + adds AI.

- [ ] FastAPI server with endpoints:
  - `GET /bills` — list/filter bills by jurisdiction, session, status, topic
  - `GET /bills/{id}` — full bill detail with text, sponsors, actions, AI summary
  - `GET /bills/{id}/text` — bill text (all versions)
  - `GET /bills/{id}/votes` — roll call records
  - `GET /bills/{id}/similar` — semantically similar bills across jurisdictions
  - `GET /search` — full-text + semantic search
  - `GET /people/{id}` — legislator detail with sponsored bills
  - `GET /jurisdictions` — list all jurisdictions
  - `GET /sessions` — list all sessions
- [ ] Implement embedding pipeline (batch embed all bill texts)
- [ ] Implement topic classification pipeline
- [ ] Set up Meilisearch for full-text search, synced from PostgreSQL
- [ ] Build ingestion scheduling (daily federal, weekly state refresh)
- [ ] Write OpenAPI spec / auto-generate docs

**Deliverable**: A functional REST API that any developer (or your own frontend) can consume. Searchable across all jurisdictions with AI enrichment.

### Phase 2: Researcher UI (Weeks 9-14)

**Goal**: Build the frontend that policy researchers actually want to use.

- [ ] Next.js app with:
  - Powerful search interface (keyword + semantic + filters)
  - Bill detail pages with AI summary, full text, version history
  - Cross-jurisdictional comparison views
  - "Research collections" — save and annotate sets of bills
  - Legislator profiles with voting records and sponsorship patterns
  - Jurisdiction dashboards (session overview, bill volume, key metrics)
- [ ] Implement the conversational research assistant (Claude-powered Q&A over your database via tool_use)
- [ ] Export capabilities (CSV, PDF reports)
- [ ] User accounts and saved searches

**Deliverable**: A usable research platform you could demo to a policy org.

### Phase 3: Intelligence Layer (Weeks 15-24)

**Goal**: Build the advanced analytical features that create real competitive differentiation.

- [ ] Cross-jurisdictional pattern detection ("model legislation" finder)
- [ ] Policy diffusion mapping (temporal spread of legislative ideas)
- [ ] Constitutional flag analysis (integrate CourtListener data)
- [ ] Bill outcome prediction (using historical passage data + features)
- [ ] Automated research reports (e.g., "2025 State of Free Speech Legislation")
- [ ] Amendment tracking and diff analysis
- [ ] Committee hearing data integration
- [ ] Regulatory cross-reference (Federal Register integration)

**Deliverable**: A platform that can produce the kind of research output that currently requires weeks of analyst time.

### Phase 4: Platform & Scale (Months 6-12)

- [ ] Multi-tenant support for different organizations
- [ ] Custom taxonomy management (let orgs define their own topic categories)
- [ ] Webhook/alert system for bill changes matching saved criteria
- [ ] API access for third-party integrations
- [ ] Historical analysis tools (multi-year trend analysis)
- [ ] Consider open-sourcing the data pipeline while monetizing the AI layer

---

## Part 5: Key Decisions & Trade-offs

### 5.1 Build vs. Use LegiScan Bulk Data

**Recommendation**: Use LegiScan bulk data as a *supplement*, not a foundation.

LegiScan's weekly datasets are useful for gap-filling and validation, but building on them as your primary source creates a dependency on their data format and update cadence. The Congress.gov API + Open States combination gives you more control, fresher data, and the ability to extend coverage (e.g., committee hearing transcripts, which LegiScan doesn't provide).

The strategic advantage of building your own ingestion pipeline is that you can add data sources LegiScan doesn't have — CRS reports, regulatory data, court opinions, campaign finance — creating a richer analytical substrate than any single-source approach.

### 5.2 Embedding Strategy

For the MVP, use OpenAI's `text-embedding-3-large` (1536 dimensions) via pgvector. It's the most cost-effective for bulk embedding and pgvector means no separate vector DB to manage.

At scale, consider fine-tuning an embedding model on legislative text for better domain-specific retrieval, or switching to Anthropic's embeddings when available.

### 5.3 LLM Cost Management

Back-of-envelope for full national coverage:

- ~175,000 bills/year × ~5,000 tokens average = ~875M input tokens
- Summarization (Sonnet): ~$2.60/M input tokens = ~$2,275/year for summaries alone
- Classification (Haiku): ~$0.25/M input tokens = ~$219/year
- With Batch API discount (50%): roughly halved
- Embeddings: ~$0.13/M tokens × 875M = ~$114/year

Total LLM costs for full pipeline: roughly **$1,500-3,000/year** at current pricing, which is extremely manageable. The real cost is compute for the ingestion pipeline and database hosting.

### 5.4 Open Source Strategy

Consider open-sourcing the data pipeline and core API, while keeping the AI analysis layer proprietary. This mirrors the Open States model and builds community trust with policy researchers. The moat is in the quality of your LLM prompts, the enrichment pipeline, and the research-oriented UX — not in the raw data access.

---

## Part 6: Competitive Positioning

| Feature | LegiScan | Plural/Open States | Quorum | **Your Tool** |
|---------|----------|-------------------|--------|---------------|
| Federal coverage | ✅ | ✅ | ✅ | ✅ |
| 50-state coverage | ✅ | ✅ | ✅ | ✅ |
| Full bill text | ✅ | Partial | ✅ | ✅ |
| AI summaries | ❌ | ✅ (basic) | ✅ | ✅ (research-grade) |
| Semantic search | ❌ | ❌ | ❌ | ✅ |
| Cross-jurisdiction similarity | ❌ | ❌ | Limited | ✅ |
| Model legislation detection | ❌ | ❌ | ❌ | ✅ |
| Constitutional flag analysis | ❌ | ❌ | ❌ | ✅ |
| Policy diffusion tracking | ❌ | ❌ | ❌ | ✅ |
| Research collections | ❌ | ❌ | ✅ | ✅ |
| Conversational research assistant | ❌ | ❌ | ❌ | ✅ |
| Open API | ✅ (gated) | ✅ | ❌ | ✅ |
| Regulatory cross-reference | ❌ | ❌ | ✅ | ✅ (Phase 3) |
| Price point | $$$$ | Free-$$ | $$$$$ | $-$$ (research orgs) |

The strategic insight: Quorum and Plural are selling to **enterprise GR teams** at $10K-50K+/year. Policy research organizations typically can't afford that. By building a tool specifically for the research use case, you serve an underserved market segment while building capabilities (semantic search, pattern detection, constitutional analysis) that the enterprise players don't have.

---

## Part 7: Getting Started Tomorrow

Here's a concrete first-weekend plan:

### Day 1: Data Foundation
```bash
# 1. Set up PostgreSQL with pgvector
docker run -d --name legis-db \
  -e POSTGRES_PASSWORD=dev \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# 2. Get an API key from Congress.gov
# https://api.congress.gov — instant, free

# 3. Get an API key from Open States
# https://open.pluralpolicy.com — free tier

# 4. Clone the unitedstates/congress scrapers
git clone https://github.com/unitedstates/congress.git

# 5. Download an Open States bulk dataset for one state
# https://open.pluralpolicy.com/data/
```

### Day 2: LLM Harness Proof of Concept
```bash
# 1. Fetch 10 bills from Congress.gov API
# 2. Fetch their text from GovInfo
# 3. Run them through a Claude summarization prompt
# 4. Store structured results in PostgreSQL
# 5. Embed the summaries with text-embedding-3-large
# 6. Run a semantic search query and verify it returns sensible results
```

If that works — and it will — you have the nucleus of the entire platform.

---

## Appendix A: Key API Endpoints Reference

### Congress.gov API
```
Base: https://api.congress.gov/v3
GET /bill                           # List bills
GET /bill/{congress}/{type}/{number} # Bill detail
GET /bill/{congress}/{type}/{number}/actions
GET /bill/{congress}/{type}/{number}/amendments
GET /bill/{congress}/{type}/{number}/cosponsors
GET /bill/{congress}/{type}/{number}/subjects
GET /bill/{congress}/{type}/{number}/text
GET /member                         # List members
GET /member/{bioguideId}            # Member detail
GET /committee                      # List committees
```

### Open States v3 API
```
Base: https://v3.openstates.org
GET /jurisdictions                  # List jurisdictions
GET /bills                          # Search bills (supports full-text query)
GET /bills/{id}                     # Bill detail
GET /people                         # Search people
GET /people/{id}                    # Person detail
```

### GovInfo API
```
Base: https://api.govinfo.gov
GET /collections/BILLS/YYYY-MM-DD   # Bills updated since date
GET /packages/{packageId}/granules  # Bill text granules
GET /packages/{packageId}/htm       # HTML text
GET /packages/{packageId}/xml       # XML text
```

## Appendix B: Useful Open Source Projects

| Project | URL | Relevance |
|---------|-----|-----------|
| unitedstates/congress | github.com/unitedstates/congress | Federal bill scrapers and data pipeline |
| openstates/openstates-scrapers | github.com/openstates/openstates-scrapers | All 50 state scrapers |
| openstates/people | github.com/openstates/people | Curated legislator data |
| unitedstates/BillMap | github.com/unitedstates/BillMap | Bill similarity and mapping tools (Demand Progress) |
| StateLegiscraper | github.com/ka-chang/StateLegiscraper | Committee hearing transcript scraper |
| congressionalrecord | judgelord.github.io/congressionalrecord | Congressional Record scraper/parser |
| legcop (PyPI) | pypi.org/project/legcop/ | Python wrapper for LegiScan API |
| pyopenstates | github.com/openstates/pyopenstates | Python client for Open States v3 |

## Appendix C: References

[^1]: Congress.gov API documentation and registration. Library of Congress. https://api.congress.gov

[^2]: Open States / Plural Open Data documentation. https://docs.openstates.org/

[^3]: LegiScan API documentation and weekly datasets. https://legiscan.com/legiscan

[^4]: unitedstates/congress — Public domain data collectors for the work of Congress. https://github.com/unitedstates/congress

[^5]: GovInfo API documentation. Government Publishing Office. https://api.govinfo.gov/docs

[^6]: Open States bulk data downloads. https://open.pluralpolicy.com/data/

[^7]: ProPublica Congress API documentation. https://projects.propublica.org/api-docs/congress-api/

[^8]: GovTrack.us data sources documentation. https://www.govtrack.us/about-our-data

[^9]: Plural Policy — AI-powered legislative intelligence platform. https://pluralpolicy.com/

[^10]: POPVOX Foundation — AI for the Legislative Branch resources. https://www.popvox.org/artificial-intelligence
