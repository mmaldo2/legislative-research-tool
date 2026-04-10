# Runtime Abstraction Proposal

> For Hermes: use subagent-driven-development if implementing this plan later.

Goal: replace provider-shaped LLM wiring with a provider-neutral runtime layer so the standalone app remains primary while supporting a ChatGPT-first MVP, direct API providers, and later local OSS models.

Architecture summary
- Keep the app/web workflows as the product shell.
- Treat search, investigations, bill detail, artifacts, and persistence as the durable tool/data plane.
- Insert a runtime abstraction between product workflows and model providers.
- Support multiple runtime modes behind one contract: ChatGPT-hosted, direct API, Claude subscription SDK, and local OSS.

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
    billing_mode: str | None = None  # api, subscription, local, hosted

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
    structured_output: bool
    streaming: bool
    tool_calling: bool
    hosted_by_user_subscription: bool
    local_model: bool

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

    async def run_agent_turns(
        self,
        *,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict],
        model: str,
        max_rounds: int,
        tool_executor: Any,
    ) -> dict[str, Any]: ...

    async def stream_agent_turns(...) -> AsyncIterator[dict[str, Any]]: ...
```

### 2. Runtime adapters

Add adapters under `src/runtime/adapters/`.

MVP adapters
- `chatgpt_hosted.py`
  - target default frontier runtime for MVP
  - app remains primary shell, but reasoning is delegated to a ChatGPT-hosted path when supported
  - if true delegated runtime is not yet fully available, ship this as an interface with a temporary “not implemented / connector-only” implementation while other adapters keep the app working
- `openai_api.py`
  - wraps direct API use
- `claude_sdk.py`
  - wraps Claude subscription SDK
- `anthropic_api.py`
  - wraps direct Anthropic API
- `local_openai_compatible.py`
  - for Ollama/vLLM/OpenAI-compatible local servers later

Important rule
- Adapters convert provider-native responses into internal contracts.
- The rest of the app never imports provider SDK types.

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
- `DEFAULT_MODEL_RUNTIME=chatgpt-hosted|openai-api|anthropic-api|claude-sdk|local-openai-compatible`
- `DEFAULT_AGENT_RUNTIME=chatgpt-hosted|claude-sdk|openai-api|local-openai-compatible`
- optional per-workspace override later
- separate model names from runtime names

Example
- `SUMMARY_MODEL=gpt-5-mini`
- `AGENT_MODEL=gpt-5`
- `LOCAL_MODEL=qwen2.5-72b-instruct`

Avoid using `LLM_PROVIDER` as the main abstraction long-term; it is too narrow.

## Migration path

### Phase 1: Extract runtime contracts without changing product behavior
1. Create `src/runtime/contracts.py`.
2. Create `src/runtime/registry.py`.
3. Implement `AnthropicApiRuntime`, `ClaudeSdkRuntime`, and `OpenAIApiRuntime` by wrapping existing adapters.
4. Change `src/api/deps.py` to resolve a `ModelRuntime` and `AgentRuntime` rather than raw SDK clients.
5. Keep existing env vars temporarily for backwards compatibility.

Success criteria
- No route imports provider SDK classes directly.
- Runtime resolution returns internal runtime objects.

### Phase 2: Refactor `LLMHarness` onto `ModelRuntime`
1. Change `LLMHarness` constructor to accept `runtime: ModelRuntime`.
2. Replace direct `client.messages.create(...)` with `runtime.generate_structured(...)` or `generate_text(...)`.
3. Move JSON parsing fallback into the runtime layer where possible.
4. Replace Anthropic response assumptions with `GenerationResult`.
5. Update cost tracking to support unknown/subscription/local billing.

Success criteria
- Analysis/report/composer flows become provider-neutral.
- `src/llm/openai_adapter.py` and `src/llm/claude_sdk_adapter.py` are no longer imported outside runtime adapters.

### Phase 3: Refactor agentic chat/workspace flows onto `AgentRuntime`
1. Replace Anthropic-specific tool loop logic in `src/services/chat_service.py`.
2. Define a provider-neutral event model for:
   - assistant text delta
   - tool requested
   - tool running
   - tool completed
   - final response
3. Move provider-specific message block parsing into agent runtime adapters.
4. Convert `RESEARCH_TOOLS` into provider-neutral tool specs.

Success criteria
- `get_agentic_client()` disappears.
- Chat/workspace flows ask for `AgentRuntime`, not a provider client.

### Phase 4: Add ChatGPT-first runtime path
There are two possible implementations:

A. True delegated hosted runtime (ideal)
- independent app shell
- user authorizes ChatGPT-linked runtime access
- app sends prompts/tool context to hosted runtime
- runtime reasons and calls back into app tools

B. Transitional split-brain mode (practical)
- web app remains primary
- MCP/ChatGPT connector is available for hosted reasoning workflows
- in-app LLM workflows continue via direct/API or subscription adapters until delegated hosted runtime is supported

Recommendation
- Design the runtime interface for A.
- Ship the product using B where needed.
- Do not contort the whole app around connector-only UX.

### Phase 5: Add local OSS runtime
Implement `LocalOpenAICompatibleRuntime` for:
- local vLLM server
- Ollama with compatible endpoints if sufficient
- other OpenAI-compatible servers

Success criteria
- same app workflows run against a local runtime without route-level changes.

## File-level proposal

Create
- `src/runtime/__init__.py`
- `src/runtime/contracts.py`
- `src/runtime/registry.py`
- `src/runtime/tools.py`
- `src/runtime/adapters/openai_api.py`
- `src/runtime/adapters/anthropic_api.py`
- `src/runtime/adapters/claude_sdk.py`
- `src/runtime/adapters/chatgpt_hosted.py`
- `src/runtime/adapters/local_openai_compatible.py`

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
- Data/workflow plane: existing API + MCP tools
- Default frontier runtime target: ChatGPT-hosted/delegated runtime path when available
- Transitional fallback runtimes: Claude SDK and direct OpenAI API
- Future local runtime: OpenAI-compatible local server adapter

This preserves the product direction without forcing an immediate connector-only future.
