---
status: complete
priority: p3
issue_id: "062"
tags: [code-review, architecture, database]
dependencies: []
---

# Collection updated_at Not Auto-Updated + Missing Alembic Migrations + Filename Sanitization

## Problem Statement

Three minor infrastructure issues: Collection.updated_at is never set on mutations, no Alembic migration files for the 4 new tables, and the Content-Disposition filename in brief export needs stricter sanitization.

## Findings

1. Collection `updated_at` has `server_default="now()"` but no `onupdate` — mutations show stale timestamps (`src/models/collection.py`)
2. No Alembic migration for `collections`, `collection_items`, `conversations`, `conversation_messages` tables
3. Brief export filename: `bill.identifier.replace(" ", "_").replace("/", "-")` doesn't sanitize quotes, newlines, or other special chars (`src/api/export.py` ~line 198)
4. Agents: Architecture Strategist (F, R9), Security Sentinel (M1)

## Proposed Solutions

### Option A: Fix all (Recommended)
- Add `onupdate=datetime.now(UTC)` to Collection.updated_at (or set explicitly in endpoints)
- Run `alembic revision --autogenerate -m "add collections and conversations"`
- Use `re.sub(r'[^a-zA-Z0-9_-]', '_', bill.identifier)` for filename
- **Effort**: Small-Medium

## Technical Details

- **Files**: `src/models/collection.py`, `src/api/export.py`, `alembic/`

## Acceptance Criteria

- [ ] Collection updated_at reflects actual last-modified time
- [ ] Alembic migration creates all 4 new tables
- [ ] Brief download filename is safe for all OS/browsers

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
