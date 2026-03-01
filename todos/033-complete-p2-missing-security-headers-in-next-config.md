---
status: complete
priority: p2
issue_id: "033"
tags: [code-review, security]
dependencies: []
---

# 033 — Missing Security Headers in next.config.ts

## Problem Statement

The `frontend/next.config.ts` file is effectively empty — it exports a default config with no customizations. The application is missing critical security headers: no Content Security Policy (CSP), no `X-Frame-Options` (clickjacking vulnerability), no `Strict-Transport-Security` (HSTS), and no `X-Content-Type-Options`. This leaves the application exposed to common web security attacks.

## Findings

- `frontend/next.config.ts` exports a minimal/empty configuration object.
- No security headers are set anywhere in the frontend configuration.
- **Missing `X-Frame-Options`**: The application can be embedded in iframes on any domain, enabling clickjacking attacks.
- **Missing `Content-Security-Policy`**: No restrictions on script sources, style sources, or other resource loading. XSS attacks have broader impact without CSP.
- **Missing `Strict-Transport-Security`**: Browsers will not enforce HTTPS-only connections, allowing downgrade attacks.
- **Missing `X-Content-Type-Options`**: Browsers may MIME-sniff responses, potentially executing non-script resources as scripts.
- **Missing `Referrer-Policy`**: Full referrer URLs may be leaked to third-party origins.
- **Missing `Permissions-Policy`**: No restrictions on browser feature access (camera, microphone, geolocation).

## Proposed Solutions

### Solution A: Add security headers via `headers()` in next.config.ts

Use Next.js's built-in `headers()` configuration function to set security headers on all routes. Start with a permissive CSP and tighten it over time.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Native Next.js feature; applies to all routes; no middleware needed; easy to maintain |
| **Cons** | CSP may need tuning if inline scripts or third-party resources are used; too-strict CSP can break functionality |
| **Effort** | Small-medium — one file change, but CSP requires careful testing |
| **Risk** | Medium — an overly strict CSP can break the application; requires testing all pages after deployment |

### Solution B: Add security headers via Next.js middleware

Create a `middleware.ts` file that injects security headers on every response. This provides more flexibility (e.g., per-route CSP) but adds a middleware layer.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Per-route header customization; dynamic CSP nonces possible; more flexible |
| **Cons** | Middleware runs on every request; more complex setup; harder to review at a glance |
| **Effort** | Medium — new middleware file, CSP nonce generation, testing |
| **Risk** | Medium — middleware complexity; performance overhead on every request |

### Recommendation

**Solution A** is the right starting point. The `headers()` config is the standard Next.js approach and covers the majority of use cases. Middleware (Solution B) is only needed if dynamic CSP nonces are required later.

## Technical Details

**Current code** (`frontend/next.config.ts`):
```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {};

export default nextConfig;
```

**Proposed change** (Solution A):
```typescript
import type { NextConfig } from "next";

const securityHeaders = [
  {
    key: "X-Frame-Options",
    value: "DENY",
  },
  {
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'", // tighten after audit
      "style-src 'self' 'unsafe-inline'",
      `connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}`,
      "img-src 'self' data:",
      "font-src 'self'",
      "frame-ancestors 'none'",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
```

## Acceptance Criteria

- [ ] `X-Frame-Options: DENY` header is present on all responses.
- [ ] `X-Content-Type-Options: nosniff` header is present on all responses.
- [ ] `Strict-Transport-Security` header is present with a reasonable max-age.
- [ ] `Referrer-Policy` header is set to `strict-origin-when-cross-origin` or stricter.
- [ ] `Permissions-Policy` restricts unused browser features.
- [ ] `Content-Security-Policy` header is present and does not break any existing functionality.
- [ ] All pages render and function correctly after headers are added.
- [ ] Security headers are verified using a tool like securityheaders.com or browser DevTools.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/next.config.ts` — Next.js configuration
- Next.js headers config: https://nextjs.org/docs/app/api-reference/next-config-js/headers
- OWASP Secure Headers Project: https://owasp.org/www-project-secure-headers/
- securityheaders.com — header verification tool
- MDN Content-Security-Policy: https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP
