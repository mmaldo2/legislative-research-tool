---
status: resolved
priority: p1
issue_id: "120"
tags: [code-review, prediction, security]
dependencies: []
---

# Pickle Deserialization Without Integrity Verification

## Problem Statement

`src/prediction/service.py` loads 9 pickle files (7 RF models, 1 meta-learner, 1 scaler) via `pickle.load()` with no integrity checks. Model artifacts are gitignored, produced by an offline script with a relative path, and cannot be audited through code review. A compromised artifact means arbitrary code execution on the server at import time.

## Findings

- Security sentinel rated HIGH: no checksums, signatures, or hash verification
- `promote.py` writes pickles to `../src/prediction/models/` (relative path, no validation)
- LightGBM models use safe text format (`.txt`) — not a concern
- `# noqa: S301` comments suppress Bandit warnings

## Proposed Solutions

### Option A: SHA-256 checksums in metadata.json (Recommended)
Have `promote.py` compute SHA-256 of each `.pkl` file and store in `metadata.json`. Have `_load_models()` verify hashes before calling `pickle.load()`.
- **Pros:** Simple, detects tampering, low effort
- **Cons:** Doesn't prevent supply chain attack if metadata is also compromised
- **Effort:** Small (15 lines in promote.py, 10 in service.py)
- **Risk:** Low

### Option B: Replace pickle with skops.io
Use `skops.io` for scikit-learn serialization with type allowlists.
- **Pros:** Eliminates arbitrary code execution risk entirely
- **Cons:** New dependency, may not support all model types
- **Effort:** Medium
- **Risk:** Medium

## Acceptance Criteria

- [ ] promote.py computes and stores SHA-256 hashes for all .pkl files in metadata.json
- [ ] service.py verifies hashes before calling pickle.load()
- [ ] Hash mismatch causes load failure with clear error message

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-18 | Created | Security sentinel rated HIGH |
