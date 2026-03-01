---
status: pending
priority: p1
issue_id: "026"
tags: [code-review, security]
dependencies: []
---

# 026 — Unvalidated External URL in Bill Text Tab

## Problem Statement

The bill text tab component at `frontend/src/app/bills/[id]/text-tab.tsx:73-80` renders `source_url` from the API response directly as an `<a href>` without validating the URL protocol. The `source_url` originates from external data sources (Open States, GovInfo). If any upstream data source is compromised or contains malformed data, URLs with `javascript:`, `data:`, or other dangerous protocols could be rendered as clickable links, enabling XSS attacks.

## Findings

- `text-tab.tsx:73-80` renders: `<a href={bill.source_url}>View source</a>` (approximate).
- The `source_url` field is populated by data ingested from external sources (Open States API, GovInfo).
- No protocol validation is performed anywhere in the data pipeline — not at ingestion, not at the API layer, and not at the rendering layer.
- Dangerous protocols include: `javascript:`, `data:`, `vbscript:`, `blob:` (in some contexts).
- Other components in the codebase that render external links do not validate protocols either, but `source_url` is the most directly user-interactive instance.

## Proposed Solutions

### Solution A: Add `isSafeUrl()` helper function

Create a small utility function that validates that a URL uses the `http:` or `https:` protocol. Use it in the text tab component (and anywhere else external URLs are rendered).

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Simple, focused, easy to understand and test; can be reused across the codebase |
| **Cons** | Must remember to use it everywhere external URLs are rendered |
| **Effort** | Small — one utility function plus one component update |
| **Risk** | None |

### Solution B: Sanitize all external URLs through a shared component

Create a `<SafeLink>` component that wraps `<a>` and performs protocol validation internally. Replace all instances of `<a href={externalUrl}>` with `<SafeLink href={externalUrl}>`.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Protocol validation is automatic for anyone using the component; harder to forget |
| **Cons** | Requires finding and replacing all external link usages; more invasive refactor |
| **Effort** | Small-to-medium — new component plus find-and-replace across templates |
| **Risk** | None |

### Recommendation

**Solution A** is recommended as the immediate fix for this P1 issue. A `<SafeLink>` component (Solution B) is a good follow-up enhancement but is not necessary to close this finding. The `isSafeUrl()` helper can be used both in a future `<SafeLink>` component and directly in templates.

## Technical Details

**Current code** (`text-tab.tsx:73-80`, approximate):
```tsx
{bill.source_url && (
  <a
    href={bill.source_url}
    target="_blank"
    rel="noopener noreferrer"
    className="text-blue-600 hover:underline"
  >
    View full text at source
  </a>
)}
```

**Proposed utility** (`lib/url.ts`):
```typescript
const SAFE_PROTOCOLS = ["http:", "https:"];

export function isSafeUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return SAFE_PROTOCOLS.includes(parsed.protocol);
  } catch {
    return false;
  }
}
```

**Updated component** (`text-tab.tsx`):
```tsx
{bill.source_url && isSafeUrl(bill.source_url) && (
  <a
    href={bill.source_url}
    target="_blank"
    rel="noopener noreferrer"
    className="text-blue-600 hover:underline"
  >
    View full text at source
  </a>
)}
```

**Dangerous URL examples blocked:**
| URL | `isSafeUrl` result |
|-----|--------------------|
| `https://leginfo.ca.gov/bill/123` | `true` |
| `http://govinfo.gov/content/pkg/...` | `true` |
| `javascript:alert('xss')` | `false` |
| `data:text/html,<script>...</script>` | `false` |
| `vbscript:MsgBox("xss")` | `false` |
| `not-a-url` | `false` |

## Acceptance Criteria

- [ ] Only `http:` and `https:` URLs are rendered as clickable `<a href>` links.
- [ ] URLs with `javascript:`, `data:`, `vbscript:`, `blob:`, or any other non-http protocol are not rendered as links.
- [ ] Malformed URLs (not parseable by `new URL()`) are not rendered as links.
- [ ] The `isSafeUrl()` utility is unit tested with the edge cases listed above.
- [ ] The link is hidden (or rendered as plain text) when the URL is unsafe, rather than throwing an error.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/app/bills/[id]/text-tab.tsx:70-83` — affected component
- OWASP XSS prevention cheat sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Scripting_Prevention_Cheat_Sheet.html
- MDN URL API: https://developer.mozilla.org/en-US/docs/Web/API/URL/URL
