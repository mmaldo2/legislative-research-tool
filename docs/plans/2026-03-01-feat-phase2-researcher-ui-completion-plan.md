---
title: "feat: Complete Phase 2 Researcher UI — Feature Gaps"
type: feat
status: completed
date: 2026-03-01
---

# Complete Phase 2 Researcher UI — Feature Gaps

## Overview

Phase 2 of the roadmap (Researcher UI) is ~75-80% complete. The search interface, bill detail pages (8 tabs), cross-jurisdictional comparison, collections, chat assistant, and CSV export are all built and working. Three feature gaps remain:

1. **Legislator Profile Enhancement** — voting records, sponsored bills, aggregate stats
2. **Jurisdiction Dashboard Metrics** — bill counts, top topics, activity summary
3. **Saved Searches** — save/name/re-run search queries from localStorage

Auth and user accounts are deferred to Phase 4. Each feature requires both backend (new endpoints/filters) and frontend work, except saved searches which is frontend-only.

## Problem Statement / Motivation

Policy researchers using the platform can search bills, view AI analysis, and compare legislation — but they can't effectively research *legislators* or *jurisdictions* as first-class entities. The legislator profile page shows only a name card. The jurisdiction page shows sessions and recent bills but no aggregate intelligence. And there's no way to save frequently-used searches for quick re-access.

These gaps matter because the target users (think tank analysts, policy researchers) work iteratively: they track specific legislators' voting patterns, monitor legislative activity by state, and re-run the same analytical queries regularly.

## Technical Approach

### Architecture

All three features follow established codebase patterns:

- **Backend**: FastAPI endpoints in `src/api/`, Pydantic schemas in `src/schemas/`, service functions in `src/services/`, async SQLAlchemy queries
- **Frontend**: Next.js App Router, server components with `Suspense` for data fetching, shadcn/ui components, TypeScript types mirroring backend schemas
- **API client**: `fetchApi<T>()` wrapper in `frontend/src/lib/api.ts` with `revalidate` caching

No new dependencies required. No new database tables. Two new indexes recommended.

### Implementation Phases

---

#### Phase 1: Legislator Profile Enhancement

**Goal**: Transform the legislator detail page from a static name card into a full research profile with sponsored bills, voting record, and aggregate statistics.

##### 1.1 Backend: Add `sponsor` filter to `GET /bills`

Add a `sponsor` query parameter to the existing bills list endpoint. This reuses the existing `BillListResponse` schema and is the minimal backend change.

**Files to modify:**

- `src/api/bills.py` — Add `sponsor: str | None = Query(None)` parameter
- `src/services/bill_service.py` — Add join through `Sponsorship` table when `sponsor` filter is present

```python
# src/services/bill_service.py — add to list_bills()
if sponsor:
    query = query.join(Bill.sponsorships).where(Sponsorship.person_id == sponsor)
```

##### 1.2 Backend: New `GET /people/{person_id}/votes` endpoint

Create a person-centric vote query endpoint returning a slimmed-down response (only this person's vote per event, not all 435 House votes).

**Files to create/modify:**

- `src/schemas/person.py` — Add `PersonVoteResponse` and `PersonVoteListResponse`
- `src/api/people.py` — Add endpoint
- `src/services/person_service.py` — Add `get_person_votes()` query

```python
# src/schemas/person.py
class PersonVoteResponse(BaseModel):
    vote_event_id: str
    bill_id: str
    bill_identifier: str
    bill_title: str
    vote_date: date | None
    chamber: str | None
    motion_text: str | None
    result: str | None
    option: str  # this person's vote: "yes", "no", "not voting", etc.

class PersonVoteListResponse(BaseModel):
    votes: list[PersonVoteResponse]
    meta: MetaResponse
```

##### 1.3 Backend: New `GET /people/{person_id}/stats` endpoint

Aggregate stats computed lazily (not embedded in the profile response for performance isolation).

**Files to modify:**

- `src/schemas/person.py` — Add `PersonStatsResponse`
- `src/api/people.py` — Add endpoint
- `src/services/person_service.py` — Add `get_person_stats()` query

```python
# src/schemas/person.py
class PersonStatsResponse(BaseModel):
    bills_sponsored: int        # primary sponsor
    bills_cosponsored: int      # cosponsor
    votes_cast: int             # total vote records
    vote_participation_rate: float | None  # votes_cast / total_vote_events in jurisdiction
```

##### 1.4 Backend: Extend `PersonResponse` with `image_url`

The `Person` model already stores `image_url` but the schema doesn't expose it.

**File to modify:**

- `src/schemas/person.py` — Add `image_url: str | None = None` to `PersonResponse`

##### 1.5 Backend: Add database index on `vote_records.person_id`

The `person_id` column is a ForeignKey but has no index. Person-centric vote queries will be slow without it.

**File to create:**

- `migrations/versions/003_add_vote_record_person_index.py` — Alembic migration

##### 1.6 Frontend: Restructure legislator detail page with tabs

Replace the static card with a tabbed layout: **Profile** (existing info + photo + stats), **Sponsored Bills**, **Voting Record**.

**Files to modify:**

- `frontend/src/app/legislators/[id]/page.tsx` — Add tabs, move detail rendering to components
- `frontend/src/types/api.ts` — Add `PersonVoteResponse`, `PersonVoteListResponse`, `PersonStatsResponse`
- `frontend/src/lib/api.ts` — Add `getPersonVotes()`, `getPersonStats()`, `listBills()` already supports new `sponsor` param

**Files to create:**

- `frontend/src/app/legislators/[id]/legislator-detail.tsx` — Main detail component with Tabs
- `frontend/src/app/legislators/[id]/sponsored-bills-tab.tsx` — Server async component fetching `listBills({sponsor: personId})`
- `frontend/src/app/legislators/[id]/voting-record-tab.tsx` — Server async component fetching `getPersonVotes()`

**Empty states:**

- "No sponsored bills found for this legislator."
- "No voting records available."

**Acceptance criteria:**

- [x]`GET /bills?sponsor={person_id}` returns bills where person is primary sponsor or cosponsor
- [x]`GET /people/{person_id}/votes` returns paginated vote records with bill context
- [x]`GET /people/{person_id}/stats` returns aggregate counts
- [x]`PersonResponse` includes `image_url`
- [x]Legislator detail page has 3 tabs: Profile, Sponsored Bills, Voting Record
- [x]Profile tab shows photo (if available), stats card, basic info
- [x]Sponsored Bills tab shows paginated bill list with primary/cosponsor badges
- [x]Voting Record tab shows paginated vote list with yes/no styling
- [x]Empty states render for legislators with no bills or votes
- [x]Jurisdiction badge on profile links to `/jurisdictions/{id}`
- [x]All new endpoints have tests
- [x]Frontend handles partial failures (profile loads, tabs show per-tab errors)

---

#### Phase 2: Jurisdiction Dashboard Metrics

**Goal**: Add an "Overview" tab to jurisdiction detail pages showing aggregate legislative intelligence.

##### 2.1 Backend: New `GET /jurisdictions/{jurisdiction_id}/stats` endpoint

A single stats endpoint that returns pre-aggregated metrics. Uses efficient SQL `GROUP BY` queries.

**Files to create/modify:**

- `src/schemas/jurisdiction.py` — Add stats response schemas
- `src/api/jurisdictions.py` — Add stats endpoint
- `src/services/jurisdiction_service.py` — Create service file with stats query

```python
# src/schemas/jurisdiction.py
class SessionBillCount(BaseModel):
    session_id: str
    session_name: str
    bill_count: int

class SubjectCount(BaseModel):
    subject: str
    count: int

class JurisdictionStatsResponse(BaseModel):
    total_bills: int
    total_legislators: int
    bills_by_status: dict[str, int]           # {"introduced": 150, "enacted": 30, ...}
    bills_by_session: list[SessionBillCount]   # ordered by session start_date desc
    top_subjects: list[SubjectCount]           # top 15, uses unnest(subject)
```

```python
# src/services/jurisdiction_service.py — key query patterns
# Bills by status:
select(Bill.status, func.count()).where(Bill.jurisdiction_id == jid).group_by(Bill.status)

# Top subjects (PostgreSQL unnest):
select(func.unnest(Bill.subject).label("subj"), func.count().label("cnt"))\
    .where(Bill.jurisdiction_id == jid)\
    .group_by("subj").order_by(desc("cnt")).limit(15)
```

##### 2.2 Frontend: Add "Overview" tab to jurisdiction detail

Add a new tab before the existing "Sessions" and "Recent Bills" tabs.

**Files to modify:**

- `frontend/src/app/jurisdictions/[id]/jurisdiction-detail.tsx` — Add Overview tab
- `frontend/src/types/api.ts` — Add `JurisdictionStatsResponse`, `SessionBillCount`, `SubjectCount`
- `frontend/src/lib/api.ts` — Add `getJurisdictionStats()`

**Files to create:**

- `frontend/src/app/jurisdictions/[id]/stats-tab.tsx` — Server async component

**UI design:**

- Stats cards row: Total Bills, Total Legislators, Bills Enacted (percentage)
- Bills by status: Horizontal bar chart or styled stat bars (CSS-only, no charting library)
- Bills by session: Simple table with session name and count
- Top subjects: Tag cloud or ranked list with count badges

**Empty states:**

- "No bill statistics available for this jurisdiction."

**Acceptance criteria:**

- [x]`GET /jurisdictions/{id}/stats` returns aggregated metrics
- [x]Overview tab shows total bills, total legislators
- [x]Bills by status displayed as visual breakdown
- [x]Bills by session displayed as a table
- [x]Top 15 subjects displayed with counts
- [x]Stats endpoint cached at 300s revalidate (data changes slowly)
- [x]Empty state when jurisdiction has no bills
- [x]Stats endpoint has tests

---

#### Phase 3: Saved Searches

**Goal**: Let researchers save, name, and re-run frequently-used search queries. Pure frontend feature using localStorage.

##### 3.1 Frontend: Create `useSavedSearches()` hook

Encapsulates all localStorage operations with SSR safety, error handling, and schema versioning.

**File to create:**

- `frontend/src/hooks/use-saved-searches.ts`

```typescript
// frontend/src/hooks/use-saved-searches.ts
interface SavedSearch {
  id: string;           // crypto.randomUUID()
  name: string;         // user-provided or auto-generated from query
  query: string;
  jurisdiction: string; // may be empty
  mode: "keyword" | "semantic" | "hybrid";
  createdAt: string;    // ISO timestamp
}

interface SavedSearchStore {
  schemaVersion: 1;
  searches: SavedSearch[];
}

function useSavedSearches() {
  // SSR guard: typeof window === "undefined"
  // Parse from localStorage key "legis-saved-searches"
  // Handle corrupted JSON gracefully (reset to empty)
  return { searches, saveSearch, deleteSearch };
}
```

##### 3.2 Frontend: Add "Save Search" button to search page

When a search has been executed (results visible), show a "Save" button that prompts for a name.

**File to modify:**

- `frontend/src/app/search/page.tsx` — Add save button (visible when results exist)
- `frontend/src/app/search/search-form.tsx` — Add save action to form area

**Interaction:**

1. User runs a search, sees results
2. Clicks "Save Search" button near the search form
3. Dialog prompts for a name (auto-filled with the query text)
4. On confirm, search params saved to localStorage
5. Toast/banner confirms save

##### 3.3 Frontend: Create saved searches page

A simple client component page listing saved searches with run/delete actions.

**Files to create:**

- `frontend/src/app/search/saved/page.tsx` — Client component reading localStorage

**UI design:**

- List of cards showing: name, query text, jurisdiction filter, search mode, saved date
- "Run" button navigates to `/search?q=...&jurisdiction=...&mode=...`
- "Delete" button removes from localStorage (no confirmation needed — low-risk, easy to re-save)
- Link back to search page

**Navigation:**

- Add a "Saved" link on the search page (near the search form, not in the main nav)
- Accessible at `/search/saved` as a sub-route of search

**Empty state:**

- "No saved searches yet. Run a search and click 'Save' to add it here."

**Acceptance criteria:**

- [x]`useSavedSearches()` hook handles localStorage read/write/delete with SSR safety
- [x]Corrupted localStorage data handled gracefully (reset to empty array)
- [x]"Save Search" button visible on search page when query params are active
- [x]Save dialog prompts for name with auto-fill from query text
- [x]`/search/saved` page lists all saved searches
- [x]"Run" action navigates to search page with saved params
- [x]"Delete" action removes search from localStorage
- [x]Empty state shown when no saved searches exist
- [x]Search page has a link to `/search/saved`

---

## Acceptance Criteria

### Functional Requirements

- [x]Legislator profile page has tabs: Profile, Sponsored Bills, Voting Record
- [x]Legislator profile shows photo, aggregate stats, sponsored bills, and voting history
- [x]Jurisdiction detail page has an Overview tab with aggregate metrics
- [x]Jurisdiction overview shows bills by status, by session, and top subjects
- [x]Users can save, view, re-run, and delete searches from the search page
- [x]All new backend endpoints return proper error responses (404, 422, 500)
- [x]All new endpoints are paginated where appropriate

### Non-Functional Requirements

- [x]New backend endpoints respond in <500ms for jurisdictions with 10K+ bills
- [x]Frontend caching: stats endpoints at 300s, votes/bills at 300s
- [x]Per-tab error handling (partial failures don't break the whole page)

### Quality Gates

- [x]All new backend endpoints have pytest tests
- [x]All new Pydantic schemas have validation tests
- [x]TypeScript types match backend schemas
- [x]Empty states render for all new data sections

## Dependencies & Prerequisites

- PostgreSQL database with existing bill, person, sponsorship, and vote data
- No new Python dependencies
- No new frontend dependencies
- Alembic for the vote_records index migration

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `unnest(subject)` slow on large jurisdictions | Medium | Medium | Add `LIMIT 15` and test with real data; consider materialized view if needed |
| `vote_records.person_id` missing index causes slow queries | High | High | Add index in migration (Phase 1.5) |
| localStorage quota exceeded | Low | Low | Each saved search is ~200 bytes; 5MB limit supports ~25K searches |
| Vote option vocabulary inconsistency | Medium | Low | Normalize display with a `formatVoteOption()` utility |

## References & Research

### Internal References

- Bill detail page (8-tab pattern): `frontend/src/app/bills/[id]/page.tsx`
- Jurisdiction detail (tab pattern): `frontend/src/app/jurisdictions/[id]/jurisdiction-detail.tsx`
- `useAnalysis<T>` hook (custom hook pattern): `frontend/src/hooks/use-analysis.ts`
- `getClientId()` localStorage pattern: `frontend/src/lib/api.ts:293-301`
- Bill service (query pattern): `src/services/bill_service.py`
- Person service: `src/services/person_service.py`
- Person model with `image_url`: `src/models/person.py:21`
- Sponsorship model: `src/models/sponsorship.py`
- VoteRecord model: `src/models/vote.py:26-40`
- Existing schemas pattern: `src/schemas/bill.py` (BillSummary vs BillDetailResponse)

### Related Work

- PR #5: Phase 2 Frontend initial build
- PR #8/#9: Phase 2 completion (comparison, collections, chat, export)
- PR #10: Phase 3 Intelligence Layer
- PR #11: Review findings cleanup
- Todo #081: Accessibility analysis tabs (resolved — `aria-busy`, `role="alert"`, `aria-live`)
