---
status: resolved
priority: p1
issue_id: "103"
tags: [code-review, security, llm]
dependencies: []
---

# Sanitize LLM Prompt Inputs — Indirect Prompt Injection Prevention

## Problem Statement

The `/trends/summary` endpoint aggregates database data and interpolates dimension values directly into the LLM prompt template without sanitization. The `dimension` field comes from `Bill.subject` (ARRAY), `Bill.jurisdiction_id`, `Bill.status`, etc. If any database field contains adversarial text (e.g., a bill subject like "Ignore all previous instructions..."), it flows into the prompt.

## Findings

- **Security Sentinel (HIGH)**: Stored/indirect prompt injection vector. An attacker who can insert bills (via ingestion pipeline or direct DB write) could manipulate the LLM narrative output.
- Exploitability: Medium — requires write access to bill metadata. Ingestion pipeline from upstream sources (GovInfo, Open States, LegiScan) is the most likely vector.

**Affected files:**
- `src/llm/harness.py` lines 546-565 (prompt construction)
- `src/llm/prompts/trend_narrative_v1.py` lines 5-15 (system prompt)

## Proposed Solutions

### Option A: Sanitize + data boundary markers (Recommended)
1. Truncate dimension values: `p.dimension[:100]` when building prompt text
2. Strip newlines from dimension values
3. Add XML-like data boundary markers in the system prompt instructing the LLM to treat content between `<data>` and `</data>` tags as raw data only
- Pros: Defense in depth, minimal code change
- Cons: Determined attacker could still craft adversarial text within 100 chars
- Effort: Small
- Risk: Low

### Option B: Allowlist dimension values
Only include dimensions that match known jurisdictions/topics.
- Pros: Maximum safety
- Cons: Breaks on new jurisdictions/topics, high maintenance
- Effort: Medium
- Risk: Medium (might filter valid data)

## Acceptance Criteria

- [ ] Dimension values truncated to max length in prompt construction
- [ ] Newlines stripped from dimension values
- [ ] System prompt includes data-boundary instructions
- [ ] Test verifies sanitization of adversarial dimension values
