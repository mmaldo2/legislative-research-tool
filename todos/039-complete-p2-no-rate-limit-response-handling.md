---
status: complete
priority: p2
issue_id: "039"
tags: [code-review, quality]
dependencies: []
---

# 039 — No Rate Limit Response Handling

## Problem Statement

The backend implements rate limiting (100 requests/minute for reads, 10 requests/minute for analysis endpoints). However, the frontend's `fetchApi` does not handle 429 (Too Many Requests) responses. When a user hits the rate limit, they receive a generic error with no indication of what happened or when they can retry. There is no retry logic, no `Retry-After` header parsing, and no user-facing rate limit feedback.

## Findings

- `frontend/src/lib/api.ts` (lines 38-41) checks `response.ok` and throws a generic error for non-OK responses.
- The backend returns 429 status codes when rate limits are exceeded, likely with a `Retry-After` header.
- The frontend treats 429 identically to any other error (500, 400, etc.).
- No toast, banner, or inline message informs the user they've been rate-limited.
- No automatic retry with backoff is attempted.
- Power users performing many searches in quick succession will hit the 100 req/min limit.
- The 10 req/min analysis limit is especially easy to hit during active research sessions.
- The current error handling may show "Not Found" (see issue #029) or a generic error for rate limit responses.

## Proposed Solutions

### Solution A: Handle 429 in fetchApi with user-facing messaging and optional retry

Add specific handling for 429 responses in `fetchApi`. Parse the `Retry-After` header if present. Throw a typed `RateLimitError` that components can catch and display appropriate messaging (e.g., "Too many requests. Please wait X seconds and try again."). Optionally implement a single automatic retry after the indicated delay.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Users understand what happened and when to retry; typed error enables granular UI handling; Retry-After parsing provides accurate wait times |
| **Cons** | Automatic retry adds complexity; need to decide retry policy (how many retries, max wait) |
| **Effort** | Small-medium — 429 detection in fetchApi, RateLimitError class, UI component for the message |
| **Risk** | Low — additive change; existing behavior is unchanged for non-429 responses |

### Solution B: Add client-side request throttling to prevent hitting limits

Implement a request queue or throttle in the frontend that limits outgoing requests to stay below the backend's rate limits. Use a token bucket or sliding window algorithm.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Prevents 429 responses entirely; smoother UX; proactive rather than reactive |
| **Cons** | Must stay in sync with backend limits; adds client-side complexity; doesn't help if limits change server-side; queued requests may feel slow |
| **Effort** | Medium-large — request queue implementation, configuration, testing |
| **Risk** | Medium — client-side limits must match server-side; mismatch causes either unnecessary throttling or still hitting 429s |

### Recommendation

**Solution A** is the practical choice. Handle 429 responses gracefully when they occur rather than trying to prevent them proactively. Most users will never hit rate limits; those who do need clear feedback. Client-side throttling (Solution B) can be added later if 429s are frequent in production.

## Technical Details

**Current code** (`frontend/src/lib/api.ts`, approximate):
```typescript
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);  // 429 treated same as any error
  }

  return response.json();
}
```

**Proposed RateLimitError class**:
```typescript
export class RateLimitError extends Error {
  public retryAfterSeconds: number | null;

  constructor(retryAfter: string | null) {
    const seconds = retryAfter ? parseInt(retryAfter, 10) : null;
    super(
      seconds
        ? `Rate limited. Please retry after ${seconds} seconds.`
        : `Rate limited. Please wait a moment and try again.`
    );
    this.name = "RateLimitError";
    this.retryAfterSeconds = Number.isNaN(seconds) ? null : seconds;
  }
}
```

**Updated fetchApi**:
```typescript
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (response.status === 429) {
    throw new RateLimitError(response.headers.get("Retry-After"));
  }

  if (!response.ok) {
    throw new ApiError(response.status, response.statusText);
  }

  return response.json();
}
```

**Example UI handling** (in a search component):
```typescript
try {
  const results = await searchBills(params);
} catch (err) {
  if (err instanceof RateLimitError) {
    toast.error(err.message);
    // Optionally disable the search button for err.retryAfterSeconds
  }
}
```

## Acceptance Criteria

- [ ] `fetchApi` detects 429 responses and throws a `RateLimitError` (or equivalent typed error).
- [ ] The `Retry-After` header is parsed when present and included in the error object.
- [ ] Users see a clear, non-technical message when rate-limited (not a generic error or 404).
- [ ] The rate limit message includes the retry wait time when the backend provides it.
- [ ] Search and analysis components handle `RateLimitError` with appropriate UI feedback.
- [ ] Non-429 errors continue to be handled as before (no regression).
- [ ] Optional: automatic single retry after the `Retry-After` delay for transparent recovery.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/lib/api.ts` — fetchApi implementation
- Backend rate limiting configuration (check `src/api/` for rate limit middleware)
- MDN Retry-After header: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Retry-After
- HTTP 429 spec: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429
- Related: Issue #029 (all errors treated as 404)
