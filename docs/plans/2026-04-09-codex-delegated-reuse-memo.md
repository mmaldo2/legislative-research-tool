# Codex Delegated Reuse Memo

Date: 2026-04-09

## Executive summary

This is excellent news.

We now have strong evidence that OpenAI supports a real ChatGPT-subscription authentication path for Codex, and that this path can likely be reused by an external local app without our product owning raw OAuth lifecycle management.

The most important conclusion is:

- We do not have to assume API keys are the only viable OpenAI path.
- A delegated-reuse architecture looks technically feasible.
- The clean version of delegated reuse is local-companion based, not pure remote-backend based.

In short:
- yes, ChatGPT-subscription-backed OpenAI access is real
- yes, Codex exposes machine-callable surfaces that make delegated reuse plausible
- yes, this can fit the product direction better than API keys or app-owned OAuth
- but the viable path is a local Codex bridge/runtime, not a pure server-side shortcut

---

## What we now know

### 1. OpenAI explicitly supports ChatGPT subscription authentication for Codex

OpenAI’s Codex authentication docs state that Codex supports two ways to sign in when using OpenAI models:
- Sign in with ChatGPT for subscription access
- Sign in with an API key for usage-based access

The same docs further state:
- Codex cloud requires ChatGPT login
- Codex CLI and IDE extension support both login methods
- ChatGPT login is the default CLI path when no valid session exists
- the browser returns an access token to the CLI or IDE extension
- Codex refreshes ChatGPT-session tokens automatically during use
- login details are cached locally

This moves the discussion from speculative to concrete.

### 2. Delegated reuse is plausible because Codex has a machine-callable local interface

Research found evidence of a real Codex app-server surface with:
- JSON-RPC 2.0
- auth/account endpoints
- thread/turn APIs
- supported stdio transport
- experimental websocket transport

There is also an experimental Python SDK for the app-server.

This matters because it means an external app can potentially talk to Codex as a local authenticated engine rather than directly implementing ChatGPT/OAuth itself.

### 3. The best delegated-reuse model is: talk to Codex, do not read Codex’s raw tokens

Codex stores local auth state and refreshes tokens itself.
That means there are two broad ways to “reuse” login state:

Good version:
- our app uses Codex app-server / SDK / supported invocation surfaces
- Codex owns login, refresh, and token persistence
- our app consumes structured auth/runtime APIs
- our app avoids directly reading/storing bearer tokens

Bad version:
- our app reads Codex auth cache / token file directly
- our app starts depending on raw token formats and local auth-file internals
- security burden increases substantially

The good version is the one we should target.

### 4. Pure remote-backend reuse is not the clean path

A remote server cannot cleanly “borrow” a user’s local Codex/ChatGPT login state unless:
- a local companion/runtime talks to the backend, or
- the user’s tokens are moved upstream somehow

That means the feasible delegated-reuse architecture is not:
- browser -> remote backend -> magically authenticated OpenAI subscription runtime

It is more like:
- browser/app shell -> local Codex bridge/runtime -> OpenAI/Codex subscription-auth execution
- optionally with remote backend as tool/data plane and system of record

This is the key architectural constraint.

### 5. Your environment already shows strong feasibility signals

Parallel investigation found:
- a Windows-side Codex CLI install exists
- `codex login status` reports a live ChatGPT login
- Codex-local auth/cache state exists already
- Codex exposes command surfaces such as:
  - `app-server`
  - `mcp`
  - `mcp-server`
  - `exec`
  - `review`

So this is not a hypothetical future capability. Your machine appears to already have the key local prerequisite: an authenticated Codex environment.

---

## Recommended architectural conclusion

The product should pursue a delegated-reuse frontier-model path built around a local Codex bridge.

### Durable architecture

1. Standalone app remains the primary shell
- investigations
- working sets
- comparisons
- evidence
- output creation
- research continuity

2. App-owned tool/data plane remains the durable system of record
- search
- bill detail
- similar bills
- collections / investigations
- artifacts / memos / outputs
- MCP surfaces where useful

3. Frontier reasoning is delegated to a local Codex runtime
- authenticated with ChatGPT subscription access
- login owned by Codex
- refresh owned by Codex
- our app talks to Codex via a supported local interface

This preserves the product thesis while avoiding API-key dependence as the default OpenAI path.

---

## Security interpretation

### Preferred security model

Best practical near-term posture:
- delegated local reuse via Codex app-server / SDK / supported runtime boundary

Why this is attractive:
- Codex owns ChatGPT login
- Codex owns token refresh
- our app does not need to implement PKCE/token lifecycle
- our app can potentially avoid direct raw-token handling entirely

### What we should avoid

We should avoid making our app depend on directly reading:
- `~/.codex/auth.json`
- cached access tokens
- cached refresh tokens

Even if technically possible, that would mean:
- we are handling sensitive bearer credentials directly
- we inherit more security burden
- we become coupled to local auth-cache formats that may change

### Security summary

Most aligned with your stated preference:
- delegated reuse through Codex-managed surfaces

Less aligned:
- app-owned OAuth

Worst tradeoff:
- raw-token-cache reuse

---

## Feasibility verdict

### Feasible now

Feasible:
- building a proof-of-concept local Codex bridge that uses existing ChatGPT-authenticated Codex state
- keeping the legislative app as the product shell
- treating Codex as the delegated reasoning runtime

### Not yet proven but plausible

Plausible, needs validation:
- whether the specific Codex app-server/SDK surfaces we need are stable enough for our MVP workflows
- whether they can support assistant/report/compare flows with acceptable latency and control
- whether app-managed tool loops can be layered cleanly over the Codex runtime boundary

### Not the right target

Not a clean fit:
- pure remote-backend-only delegated reuse with no local runtime/companion

---

## What this means for current product decisions

### We should stop assuming API-key OpenAI is the only serious OpenAI path

That assumption is now outdated.
OpenAI’s own Codex docs give us a real subscription-auth route.

### We should not jump immediately to app-owned OAuth

App-owned OAuth is cleaner in some long-term product senses, but it introduces:
- more security responsibility
- more auth/token code
- more implementation complexity

Given that delegated reuse appears viable, it should be evaluated first.

### We should not let the current Claude SDK pain distort the OpenAI decision

Claude SDK may still be worth fixing as an alternative path.
But OpenAI now has a much stronger subscription-auth story than “just use API keys,” and that changes the strategic comparison.

---

## Recommended next engineering move

### Build a delegated-reuse feasibility prototype

The next step should be a proof-of-concept, not a full product rewrite.

Goal:
- verify that a local Codex-authenticated runtime can serve as the frontier reasoning engine for the legislative tool without our app directly handling tokens

### Prototype target

Prototype the smallest vertical slice around:
- local Codex bridge/runtime
- one authenticated reasoning flow
- one app-owned tool/data flow

Best candidate use case:
- investigation-aware assistant over a small working set

Why:
- it exercises the core product loop
- it tests whether Codex can be used as the local reasoning shell while the app remains the system of record

### Questions the prototype must answer

1. Can we invoke Codex through a supported local interface reliably?
2. Can we avoid direct token handling?
3. Can the app pass investigation context and receive useful responses?
4. Can the tool/data plane remain app-owned?
5. Is latency/reliability acceptable for MVP-level use?

---

## Proposed proof-of-concept boundary

A promising POC shape is:

- Windows-local Codex runtime
- Codex-authenticated via existing ChatGPT login
- local bridge process speaks to Codex via app-server/SDK/supported invocation
- legislative app remains the UI + tool/data plane
- bridge is responsible only for delegated reasoning calls

This is much more attractive than trying to thread subscription auth through the existing OpenAI API-key adapter.

---

## Risks and unknowns

1. Codex local integration surfaces are promising, but some are still marked experimental.
2. There may be friction between Windows-local Codex and WSL/backend execution paths.
3. We still need to prove which invocation surface is the most stable:
   - app-server
   - Python SDK
   - CLI exec/review
4. We need to verify how well Codex can support our app-managed tool orchestration model.
5. Prediction remains a separate issue entirely; this memo concerns frontier reasoning auth/runtime, not ML artifact delivery.

---

## Recommendation

Proceed with a delegated-reuse proof-of-concept.

Recommended strategic stance:
- primary shell: standalone legislative research app
- durable boundary: app-owned tool/data plane
- frontier model path: delegated local Codex runtime using ChatGPT subscription auth
- avoid API-key dependence as the default OpenAI story
- avoid app-owned OAuth unless delegated reuse proves inadequate

This is the strongest product/security compromise we have found so far.

---

## One-sentence conclusion

We now have enough evidence to treat local Codex-based delegated ChatGPT-auth reuse as a serious, security-aligned candidate for the MVP frontier-model path, and it is worth prototyping before committing to either API-key dependence or app-owned OAuth.
