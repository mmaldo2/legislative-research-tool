/**
 * SSE (Server-Sent Events) client for streaming LLM responses.
 *
 * Parses the custom SSE event format used by the backend:
 * - event: token    — incremental text from the LLM
 * - event: tool_status — tool call progress during agentic chat
 * - event: error    — error with type classification and retryability
 * - event: done     — final structured result with metadata
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

// --- Event types ---

export interface StreamTokenEvent {
  type: "token";
  text: string;
}

export interface StreamToolStatusEvent {
  type: "tool_status";
  tool: string;
  status: "running" | "complete";
  description: string;
}

export interface StreamErrorEvent {
  type: "error";
  message: string;
  retryable: boolean;
  error_type: "rate_limit" | "server" | "timeout" | "content_policy";
  detail?: string;
}

export interface StreamDoneEvent {
  type: "done";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metadata?: Record<string, any>;
  text?: string;
  conversation_id?: string;
  generation_id?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tool_calls?: Array<Record<string, any>>;
  cached?: boolean;
}

export type StreamEvent =
  | StreamTokenEvent
  | StreamToolStatusEvent
  | StreamErrorEvent
  | StreamDoneEvent;

// --- Client headers ---

function getClientId(): string {
  if (typeof window === "undefined") return "server";
  let id = localStorage.getItem("legis-client-id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("legis-client-id", id);
  }
  return id;
}

function buildHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Client-Id": getClientId(),
  };
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }
  return headers;
}

// --- SSE parser ---

function parseSSEEvent(eventType: string, data: string): StreamEvent | null {
  try {
    const parsed = JSON.parse(data);
    switch (eventType) {
      case "token":
        return { type: "token", text: parsed.text ?? "" };
      case "tool_status":
        return {
          type: "tool_status",
          tool: parsed.tool ?? "",
          status: parsed.status ?? "running",
          description: parsed.description ?? "",
        };
      case "error":
        return {
          type: "error",
          message: parsed.message ?? "Unknown error",
          retryable: parsed.retryable ?? false,
          error_type: parsed.error_type ?? "server",
          detail: parsed.detail,
        };
      case "done":
        return {
          type: "done",
          metadata: parsed.metadata,
          text: parsed.text,
          conversation_id: parsed.conversation_id,
          generation_id: parsed.generation_id,
          tool_calls: parsed.tool_calls,
          cached: parsed.cached,
        };
      default:
        return null;
    }
  } catch {
    return null;
  }
}

/**
 * Stream a POST request that returns SSE events.
 *
 * @param path - API path (e.g., "/chat/stream")
 * @param body - JSON body to send
 * @param signal - Optional AbortSignal for cancellation
 * @returns AsyncGenerator yielding typed StreamEvent objects
 */
export async function* streamFetch(
  path: string,
  body: Record<string, unknown>,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(
      `Stream request failed: ${response.status} ${text || response.statusText}`,
    );
  }

  if (!response.body) {
    throw new Error("Response body is null — streaming not supported");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse complete SSE events from the buffer
      // SSE events are separated by double newlines
      const parts = buffer.split("\n\n");
      // Keep the last part as it may be incomplete
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        if (!part.trim()) continue;

        let eventType = "message";
        let data = "";

        for (const line of part.split("\n")) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            data = line.slice(6);
          }
        }

        if (data) {
          const event = parseSSEEvent(eventType, data);
          if (event) {
            yield event;
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// --- Convenience functions ---

export async function* streamChat(
  message: string,
  conversationId?: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  yield* streamFetch(
    "/chat/stream",
    { message, conversation_id: conversationId },
    signal,
  );
}

export async function* streamWorkspaceChat(
  workspaceId: string,
  message: string,
  conversationId?: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  yield* streamFetch(
    `/policy-workspaces/${encodeURIComponent(workspaceId)}/chat/stream`,
    { message, conversation_id: conversationId },
    signal,
  );
}

export async function* streamCompose(
  workspaceId: string,
  sectionId: string,
  actionType: string,
  instructionText?: string,
  selectedText?: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  yield* streamFetch(
    `/policy-workspaces/${encodeURIComponent(workspaceId)}/sections/${encodeURIComponent(sectionId)}/compose/stream`,
    {
      action_type: actionType,
      instruction_text: instructionText,
      selected_text: selectedText,
    },
    signal,
  );
}
