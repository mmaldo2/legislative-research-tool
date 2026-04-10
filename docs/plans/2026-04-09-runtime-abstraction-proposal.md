# Runtime Abstraction Proposal

> For Hermes: use subagent-driven-development if implementing this plan later.

Goal: replace provider-shaped LLM wiring with an app-owned, provider-neutral execution layer so the standalone app remains primary while supporting durable app-owned tools/workflows, current subscription/API runtimes, and later local OSS models.

Architecture summary
- Keep the app/web workflows as the product shell.
- Treat search, investigations, bill detail, artifacts, persistence, and MCP-exposed operations as the canonical app-owned tool/data plane.
- Insert runtime-neutral orchestration between product workflows and model providers.
- Support multiple runtime modes behind app-owned contracts: Anthropic API, Claude subscription SDK, OpenAI generation, and later local OpenAI-compatible runtimes.
- Keep future hosted/delegated ChatGPT-style reasoning as a compatibility target, not the defining MVP adapter.

## Architectural frame: 3 durable layers

1. Canonical app-owned tool/data plane
- Existing API handlers, services, DB models, caches, and MCP tools.
- This is the durable product boundary and system of record.
- Tool execution should remain app-owned.

2. Runtime-neutral orchestrators
- Structured generation orchestration for harness/report/composer flows.
- Chat/tool orchestration for assistant/workspace flows.
- These orchestrators consume canonical internal tool/event schemas, not provider SDK types.

3. Runtime adapters
- Thin translation layers that map internal contracts to provider-native APIs/SDKs.
- Adapters translate request/response shapes only.
- They should not absorb app workflow logic or durable tool orchestration.

## Current-state findings

Primary provider coupling
- `src/api/deps.py`
  - Chooses providers with `settings.llm_provider`.
  - `openai` requires `OPENAI_API_KEY`.
  - `anthropic` requires `ANTHROPIC_API_KEY`.
  - `claude-sdk` is the only subscription-auth path today.
  - `get_agentic_client()` explicitly rejects `openai` for tool-using chat/workspace flows.
- `src/llm/openai_adapter.py`
  - Wraps `AsyncOpenAI(api_key=...)`.
  - Mimics Anthropic `messages.create/stream` shape rather than defining a provider-neutral contract.
- `src/llm/claude_sdk_adapter.py`
  - Also mimics Anthropic client shape.
  - Good proof that non-API auth can work, but still trapped behind Anthropic-style interfaces.

Harness coupling
- `src/llm/harness.py`
  - Core app logic depends on `client.messages.create(...)` and Anthropic-like response objects.
  - Parses `response.content[0].text`, `response.usage.input_tokens`, `response.stop_reason`.
  - This makes the harness provider-adapter aware instead of runtime-contract aware.
- `src/llm/cost_tracker.py`
  - Pricing table is Claude-only and assumes API-billed token accounting.

Agentic chat coupling
- `src/services/chat_service.py`
  - Uses Anthropic-style tool use directly: `stop_reason == "tool_use"`, `block.type == "tool_use"`, `tool_result` message format.
  - Accepts a concrete Anthropic client, not a generic agent runtime.
- `src/llm/tools.py`
  - Tool specs are written in Anthropic tool schema (`input_schema`), not a generic internal tool schema.
- `src/api/chat.py` and `src/api/policy_workspaces.py`
  - Depend on `get_agentic_client()` or `get_llm_harness()`.
  - Product routes therefore know too much about provider/runtime distinctions.

Parallel runtime track already exists
- `src/mcp/http_app.py`
  - Exposes the data/workflow plane via MCP for ChatGPT.
  - This is the cleanest proof that the backend can act as a provider-neutral tool server.
- `src/agents/qa_agent.py`
  - Starts a separate OpenAI Agents SDK path, but this is isolated and currently still key-based.

## Target runtime model

Introduce an internal runtime contract, e.g. `src/runtime/`.

### 1. Core contracts

Create provider-neutral interfaces:

- `ModelRuntime`
  - single-shot structured generation for analysis/report/composer tasks
- `AgentRuntime`
  - tool-using conversational loop support
- `RuntimeRegistry`
  - resolves configured runtime for a request/workspace/user
- `RuntimeCapabilities`
  - describes what a runtime supports

Example contract sketch

```python
from dataclasses import dataclass
from typing import Any, AsyncIterator
from pydantic import BaseModel

@dataclass
class UsageInfo:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    billing_mode: str | None = None  # api, subscription, local, hosted, unknown

@dataclass
class GenerationResult:
    text: str
    usage: UsageInfo
    provider: str
    model: str
    finish_reason: str | None = None
    raw: Any | None = None

@dataclass
class RuntimeCapabilities:
    structured_generation: bool
    native_tool_calling: bool
    app_managed_tool_loop: bool
    streaming_text: bool
    accurate_usage_reporting: bool
    subscription_auth: bool
    local_model: bool

@dataclass
class AssistantEvent:
    type: str  # text_delta | tool_request | tool_result | done | error
    payload: dict[str, Any]

class ModelRuntime:
    name: str
    capabilities: RuntimeCapabilities

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
    ) -> GenerationResult: ...

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        output_type: type[BaseModel],
        max_tokens: int,
    ) -> tuple[BaseModel, GenerationResult]: ...

class AgentRuntime:
    name: str
    capabilities: RuntimeCapabilities

    async def next_response(
        self,
        *,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict],
        model: str,
        max_tokens: int,
    ) -> list[AssistantEvent]: ...

    async def stream_response(...) -> AsyncIterator[AssistantEvent]: ...
```

Boundary note
- Orchestrators own the durable app workflow loop, tool execution, retries, and state transitions.
- `AgentRuntime` only translates between app-owned messages/tools/events and provider-native request/response semantics.

### 2. Runtime adapters

Add adapters under `src/runtime/adapters/`.

First-pass adapters
- `anthropic_api.py`
  - wraps direct Anthropic API
- `claude_sdk.py`
  - wraps Claude subscription SDK
- `openai_api.py`
  - wraps direct OpenAI API, initially for generation-oriented flows
  - this is a tactical generation path, not the intended long-term primary frontier-runtime strategy
- `local_openai_compatible.py`
  - for Ollama/vLLM/OpenAI-compatible local servers later

Future target adapter
- `chatgpt_hosted.py`
  - reserved for a future hosted/delegated runtime path once the mechanics are concrete
  - do not let this speculative path define the MVP runtime shape

Important rules
- Adapters convert provider-native responses into internal contracts.
- The rest of the app never imports provider SDK types.
- Adapters should not own app workflow logic, canonical tool execution, or long-lived orchestration.

### 3. Internal tool schema

Create a provider-neutral internal tool definition, e.g. `src/runtime/tools.py`.

```python
@dataclass
class RuntimeTool:
    name: str
    description: str
    json_schema: dict[str, Any]
```

Then provide conversion helpers:
- `to_anthropic_tools(tools)`
- `to_openai_tools(tools)`
- `to_mcp_tools(tools)` if needed

This removes Anthropic schema from `src/llm/tools.py` and makes tools reusable across:
- in-app assistant
- ChatGPT-hosted MCP paths
- OpenAI Agents SDK paths
- local runtimes with tool support

### 4. Runtime selection policy

Move runtime selection out of provider-specific dependency helpers and into a registry.

Suggested config split
- `DEFAULT_MODEL_RUNTIME=anthropic-api|claude-sdk|openai-api|local-openai-compatible`
- `DEFAULT_AGENT_RUNTIME=anthropic-api|claude-sdk|local-openai-compatible`
- optional per-workspace override later
- separate model names from runtime names

Example
- `SUMMARY_MODEL=gpt-5-mini`
- `AGENT_MODEL=claude-sonnet-4-6`
- `LOCAL_MODEL=qwen2.5-72b-instruct`

Avoid using `LLM_PROVIDER` as the main abstraction long-term; it is too narrow.

### 5. Capability model

Model/runtime differences in this repo are not just provider differences; they are execution-model differences.

Recommended capability flags should distinguish:
- `structured_generation`
- `native_tool_calling`
- `app_managed_tool_loop`
- `streaming_text`
- `accurate_usage_reporting`
- `subscription_auth`
- `local_model`

A single `tool_calling: bool` capability is too weak for safe migration decisions.

## Migration path

### Phase 1: Establish canonical internal tool schema + minimal runtime contracts
1. Create `src/runtime/tools.py` with canonical app-owned tool definitions.
2. Add projection helpers for Anthropic/OpenAI/MCP shapes.
3. Create `src/runtime/contracts.py` and `src/runtime/registry.py`.
4. Change `src/api/deps.py` to resolve runtime objects rather than raw SDK clients.
5. Keep existing env vars temporarily for backwards compatibility.

Success criteria
- Internal tool definitions are no longer Anthropic-shaped.
- No route needs a raw provider SDK client.
- MCP and in-app assistant code can converge on one canonical tool definition set.

### Phase 2: Normalize current Anthropic API + Claude SDK behavior behind contracts
1. Implement `AnthropicApiRuntime` and `ClaudeSdkRuntime`.
2. Preserve current behavior while moving provider request/response translation into adapters.
3. Treat Claude subscription auth as a first-class capability difference, not just another provider name.

Success criteria
- Existing Anthropic/Claude-backed behavior still works.
- Provider-specific logic is increasingly isolated in adapters.

### Phase 3: Refactor `LLMHarness` onto generation runtime
1. Change `LLMHarness` constructor to accept `runtime: ModelRuntime`.
2. Replace direct `client.messages.create(...)` with `runtime.generate_structured(...)` or `generate_text(...)`.
3. Move JSON parsing fallback into the runtime layer where possible.
4. Replace Anthropic response assumptions with `GenerationResult`.
5. Update cost tracking to support unknown/subscription/local billing and optional usage metadata.

Success criteria
- Analysis/report/composer flows become provider-neutral.
- Usage accounting is treated as optional metadata, not guaranteed API-token accounting.

### Phase 4: Refactor chat/workspace flows into runtime-neutral orchestration
1. Replace Anthropic-specific tool loop logic in `src/services/chat_service.py`.
2. Define canonical app-owned chat/tool events for:
   - assistant text delta
   - tool requested
   - tool running
   - tool completed
   - final response
3. Keep tool execution app-owned.
4. Move only provider-native message/block translation into adapters.

Success criteria
- `get_agentic_client()` disappears.
- Chat/workspace flows ask for `AgentRuntime`, not a provider client.
- `AgentRuntime` does not just rename Anthropic semantics; it supports app-managed orchestration cleanly.

### Phase 5: Add OpenAI generation path + local OpenAI-compatible path
1. Add `OpenAIApiRuntime`, initially focused on generation-oriented flows.
2. Add `LocalOpenAICompatibleRuntime` for local vLLM/Ollama-style servers.
3. Expand agentic parity only where the execution model is proven and worth the complexity.

Success criteria
- Same generation workflows run via OpenAI API or local OpenAI-compatible backends without route-level changes.

### Phase 6: Add future hosted/delegated runtime path only when concrete
Possible future target
- independent app shell
- user authorizes ChatGPT-linked runtime access
- app sends prompts/tool context to hosted runtime
- runtime reasons and calls back into app tools

Until that path is operationally concrete:
- keep MCP/ChatGPT as an interoperability surface
- do not let speculative hosted-runtime mechanics drive the MVP design

## File-level proposal

Create
- `src/runtime/__init__.py`
- `src/runtime/contracts.py`
- `src/runtime/registry.py`
- `src/runtime/tools.py`
- `src/runtime/adapters/openai_api.py`
- `src/runtime/adapters/anthropic_api.py`
- `src/runtime/adapters/claude_sdk.py`
- `src/runtime/adapters/local_openai_compatible.py`

Future target
- `src/runtime/adapters/chatgpt_hosted.py`
  - add only when the hosted/delegated runtime mechanics are concrete enough to implement safely

Refactor
- `src/api/deps.py`
  - return runtime objects, not SDK clients
- `src/llm/harness.py`
  - depend on `ModelRuntime`
- `src/services/chat_service.py`
  - depend on `AgentRuntime`
- `src/llm/tools.py`
  - replace Anthropic schema with internal tool schema
- `src/llm/cost_tracker.py`
  - support provider/runtime metadata beyond API-priced tokens
- `src/api/chat.py`
- `src/api/policy_workspaces.py`
- `src/api/reports.py`
- `src/agents/qa_agent.py`
  - either move under the runtime system later or keep explicitly experimental

## Architectural rules to enforce

1. Product code may not import provider SDKs directly.
2. Provider SDK response types must be normalized inside adapters only.
3. Tool schemas must be provider-neutral internally.
4. Runtime selection must be independent from route/business logic.
5. Cost/billing metadata must allow `unknown`, `subscription`, and `local`, not just API token pricing.
6. The standalone app remains the primary shell even when ChatGPT-hosted reasoning is used.

## MVP recommendation

For MVP, optimize for this stack:
- App shell: existing standalone web app
- Data/workflow plane: existing API + canonical internal tools + MCP interoperability
- Primary stable runtimes: Anthropic API and Claude SDK
- Added generation path: OpenAI API where useful
- Future local runtime: OpenAI-compatible local server adapter
- Future hosted/delegated target: ChatGPT-style runtime only when the mechanics are concrete

This preserves the product direction, strengthens the app-owned boundary, and avoids forcing the MVP to depend on a speculative hosted-runtime path.
