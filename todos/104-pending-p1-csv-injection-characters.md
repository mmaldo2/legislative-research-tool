---
status: pending
priority: p1
issue_id: "104"
tags: [code-review, security]
dependencies: []
---

# Expand CSV Injection Sanitization Character Set

## Problem Statement

The `_sanitize_csv()` regex `^[=+\-@\t\r]` is missing dangerous prefix characters per OWASP guidance: `|` (pipe — macOS command execution in some spreadsheets) and `;` (DDE commands). The Content-Disposition header also lacks RFC 6266 filename quoting.

## Findings

- **Security Sentinel (HIGH)**: CSV injection bypass via `|` and `;` prefix characters.
- **Security Sentinel (MEDIUM)**: Content-Disposition filename not quoted per RFC 6266.

**Affected files:**
- `src/api/trends.py` lines 25-32, 47-52
- `src/api/export.py` lines 20-28 (same issue exists here)

## Proposed Solutions

### Option A: Expand regex + quote filenames (Recommended)
1. Update regex to: `^[=+\-@\t\r|;]`
2. Quote filename in Content-Disposition: `filename="bill_trends.csv"`
3. Apply fix in both `trends.py` and `export.py` (or extract to shared util per todo #105)
- Pros: Covers OWASP-recommended character set, RFC-compliant headers
- Cons: None
- Effort: Small
- Risk: Low

## Acceptance Criteria

- [ ] Regex includes `|` and `;` as dangerous prefixes
- [ ] Content-Disposition filename is quoted per RFC 6266
- [ ] Tests cover all dangerous prefix characters (`=`, `+`, `-`, `@`, `|`, `;`)
- [ ] Fix applied in both `trends.py` and `export.py` (or shared utility)
