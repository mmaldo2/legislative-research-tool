---
status: pending
priority: p1
issue_id: "023"
tags: [code-review, security]
dependencies: []
---

# 023 — Environment Variable Leaked in Error UI

## Problem Statement

The search results component at `frontend/src/app/search/search-results.tsx:25` renders `process.env.NEXT_PUBLIC_API_URL` directly in user-facing error messages. This exposes internal infrastructure details — hostnames, ports, and paths — to end users. All other error components in the codebase use generic messages without embedding the URL, making this an inconsistency as well as a security issue.

## Findings

- `search-results.tsx:25` includes the API URL in the error message displayed to users, e.g., `"Failed to connect to {NEXT_PUBLIC_API_URL}"`.
- The `NEXT_PUBLIC_API_URL` value typically contains internal hostnames, port numbers, and path prefixes that reveal infrastructure topology.
- Other error-handling components in the codebase (e.g., bill detail, legislator pages) use generic messages like "Service unavailable" without leaking environment details.
- The value is available at build time and baked into the client JS bundle regardless, but rendering it prominently in the UI makes it trivially discoverable.

## Proposed Solutions

### Solution A: Replace with generic error message

Remove the URL from the error message entirely. Display a user-friendly message such as "The backend service is currently unavailable. Please try again later."

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Zero information leakage; consistent with other error components; simplest fix |
| **Cons** | Developers lose at-a-glance debugging info in the UI (but still have browser console and network tab) |
| **Effort** | Small — single line change |
| **Risk** | None |

### Solution B: Gate behind development-only check

Wrap the URL display in a `process.env.NODE_ENV === "development"` check so the detailed message only appears during local development. In production, show the generic message.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Preserves developer convenience in local dev; no leakage in production |
| **Cons** | Slightly more code; `NODE_ENV` check is a pattern that can be forgotten or copied incorrectly |
| **Effort** | Small — conditional wrapper around the message |
| **Risk** | Low — if someone misconfigures `NODE_ENV`, the URL could leak |

### Recommendation

**Solution A** is preferred. The URL provides minimal debugging value in the UI when developers already have browser DevTools available. Keeping error messages generic and consistent across all components is the cleaner approach.

## Technical Details

**Current code** (`search-results.tsx:23-27`, approximate):
```tsx
} catch (error) {
  return (
    <ErrorMessage
      message={`Failed to fetch results from ${process.env.NEXT_PUBLIC_API_URL}`}
    />
  );
}
```

**Proposed change** (Solution A):
```tsx
} catch (error) {
  return (
    <ErrorMessage
      message="The search service is currently unavailable. Please try again later."
    />
  );
}
```

**Proposed change** (Solution B):
```tsx
} catch (error) {
  const detail =
    process.env.NODE_ENV === "development"
      ? ` (${process.env.NEXT_PUBLIC_API_URL})`
      : "";
  return (
    <ErrorMessage
      message={`The search service is currently unavailable.${detail} Please try again later.`}
    />
  );
}
```

## Acceptance Criteria

- [ ] No internal URLs, hostnames, or port numbers are rendered in production error messages.
- [ ] The error message is user-friendly and actionable (e.g., "try again later").
- [ ] Consistent error messaging style with other error components in the codebase.
- [ ] If Solution B is chosen: URL is only shown when `NODE_ENV === "development"`.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/app/search/search-results.tsx` — affected component
- OWASP information leakage guidance: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/08-Testing_for_Error_Handling/
