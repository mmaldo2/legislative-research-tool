---
status: pending
priority: p1
issue_id: "002"
tags: [code-review, security]
dependencies: []
---

# CORS Wildcard with Credentials Enabled

## Problem Statement

`src/api/app.py` configures CORS with `allow_origins=["*"]` AND `allow_credentials=True`. This is a security misconfiguration — browsers will reject credentialed cross-origin requests when the origin is `*`, but it signals a lack of security posture. More critically, if auth is added later, this config would need to change.

## Findings

- **security-sentinel (C1)**: Wildcard CORS with credentials is explicitly forbidden by the CORS spec
- **architecture-strategist**: CORS config should be environment-specific
- **kieran-python-reviewer**: Flagged as misconfiguration

**Affected file:** `src/api/app.py:8-9`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  # contradicts wildcard origin
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Proposed Solutions

### Option A: Environment-based CORS (Recommended)
- Read allowed origins from `CORS_ORIGINS` env var
- Default to `http://localhost:3000` for dev
- Remove `allow_credentials=True` if not needed, or pair with explicit origins
- **Effort**: Small
- **Risk**: Low

### Option B: Remove credentials flag
- Keep `allow_origins=["*"]` for open API but drop `allow_credentials=True`
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] CORS origins are configurable via environment variable
- [ ] `allow_credentials=True` only used with explicit origin list
- [ ] Production config does not use wildcard origins
