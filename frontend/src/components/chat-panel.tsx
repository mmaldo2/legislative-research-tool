"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  getWorkspaceConversations,
  getConversation,
} from "@/lib/api";
import { streamChat, streamWorkspaceChat } from "@/lib/sse";
import type { StreamEvent } from "@/lib/sse";
import type { ChatMessageResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, Bot, User, Loader2, Search, FileText, Scale } from "lucide-react";

const TOOL_ICONS: Record<string, React.ReactNode> = {
  search_bills: <Search className="h-3 w-3" />,
  get_bill_detail: <FileText className="h-3 w-3" />,
  find_similar_bills: <Scale className="h-3 w-3" />,
  list_jurisdictions: <FileText className="h-3 w-3" />,
};

interface ChatPanelProps {
  workspaceId?: string;
  className?: string;
  placeholder?: string;
  emptyMessage?: string;
  /** Callback when the assistant suggests language (blockquote pattern) */
  onSuggestion?: (text: string) => void;
}

export function ChatPanel({
  workspaceId,
  className = "",
  placeholder = "Ask about legislation...",
  emptyMessage,
  onSuggestion,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [initialLoaded, setInitialLoaded] = useState(false);
  // Streaming state
  const [streamingText, setStreamingText] = useState("");
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  // Load existing workspace conversation on mount
  useEffect(() => {
    if (!workspaceId || initialLoaded) return;
    setInitialLoaded(true);

    void (async () => {
      try {
        const data = await getWorkspaceConversations(workspaceId);
        if (data.conversations.length > 0) {
          const convId = data.conversations[0].id;
          setConversationId(convId);
          // Load message history for persistence across page refreshes
          try {
            const conv = await getConversation(convId);
            if (conv.messages?.length) {
              setMessages(conv.messages);
            }
          } catch {
            // Failed to load history — start fresh
          }
        }
      } catch {
        // No existing conversation — that's fine
      }
    })();
  }, [workspaceId, initialLoaded]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessageResponse = {
      role: "user",
      content: text,
      tool_calls: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setStreamingText("");
    setToolStatus(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const stream = workspaceId
        ? streamWorkspaceChat(workspaceId, text, conversationId, controller.signal)
        : streamChat(text, conversationId, controller.signal);

      let accumulatedText = "";
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let toolCalls: Array<Record<string, any>> = [];

      for await (const event of stream) {
        if (controller.signal.aborted) break;

        switch (event.type) {
          case "token":
            accumulatedText += event.text;
            setStreamingText(accumulatedText);
            break;

          case "tool_status":
            if (event.status === "running") {
              setToolStatus(event.description);
            } else {
              setToolStatus(null);
            }
            break;

          case "done":
            if (event.conversation_id) {
              setConversationId(event.conversation_id);
            }
            if (event.text) {
              accumulatedText = event.text;
            }
            toolCalls = event.tool_calls ?? [];
            break;

          case "error":
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: event.retryable
                  ? `${event.message} You can try sending your message again.`
                  : event.message,
                tool_calls: null,
                created_at: new Date().toISOString(),
              },
            ]);
            setStreamingText("");
            setToolStatus(null);
            setLoading(false);
            return;
        }
      }

      // Finalize: add the complete assistant message
      const finalMsg: ChatMessageResponse = {
        role: "assistant",
        content: accumulatedText,
        tool_calls: toolCalls.length > 0
          ? toolCalls.map((tc) => ({
              tool_name: tc.tool_name ?? "",
              arguments: tc.arguments ?? {},
              result_summary: tc.result_summary ?? "",
            }))
          : null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, finalMsg]);
      setStreamingText("");

      // Check for suggestion blockquotes
      if (onSuggestion && accumulatedText) {
        const idx = accumulatedText.indexOf("> Suggested language:");
        if (idx !== -1) {
          const rest = accumulatedText.slice(idx + "> Suggested language:".length);
          const endIdx = rest.indexOf("\n\n");
          const suggested = endIdx !== -1 ? rest.slice(0, endIdx) : rest;
          onSuggestion(suggested.trim());
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Sorry, I encountered an error. Please try again.",
            tool_calls: null,
            created_at: new Date().toISOString(),
          },
        ]);
      }
      setStreamingText("");
    } finally {
      setToolStatus(null);
      setLoading(false);
      abortControllerRef.current = null;
    }
  }, [input, loading, workspaceId, conversationId, onSuggestion]);

  // Cleanup on unmount — cancel any in-flight stream
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const defaultEmpty = workspaceId
    ? "Ask questions about your draft, precedent bills, or legislative research."
    : 'Try asking: "What states have introduced data privacy bills?"';

  return (
    <div className={`flex flex-col ${className}`}>
      <ScrollArea className="flex-1 rounded-lg border p-3 mb-3">
        <div className="space-y-3">
          {messages.length === 0 && !streamingText && (
            <div className="text-center py-8 text-muted-foreground">
              <Bot className="mx-auto h-10 w-10 mb-3 opacity-50" />
              <p className="text-xs">{emptyMessage || defaultEmpty}</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-2 ${msg.role === "user" ? "justify-end" : ""}`}
            >
              {msg.role === "assistant" && (
                <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="h-3.5 w-3.5 text-primary" />
                </div>
              )}
              <div className={`max-w-[85%] ${msg.role === "user" ? "order-first" : ""}`}>
                <Card
                  className={
                    msg.role === "user" ? "bg-primary text-primary-foreground" : ""
                  }
                >
                  <CardContent className="p-2.5">
                    <p className="text-xs whitespace-pre-wrap leading-relaxed">
                      {msg.content}
                    </p>
                  </CardContent>
                </Card>
                {msg.tool_calls && msg.tool_calls.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {msg.tool_calls.map((tc, j) => (
                      <Badge key={j} variant="outline" className="text-[10px] gap-0.5 py-0">
                        {TOOL_ICONS[tc.tool_name] ?? <Search className="h-2.5 w-2.5" />}
                        {tc.tool_name.replace(/_/g, " ")}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
              {msg.role === "user" && (
                <div className="flex-shrink-0 w-7 h-7 rounded-full bg-muted flex items-center justify-center">
                  <User className="h-3.5 w-3.5" />
                </div>
              )}
            </div>
          ))}

          {/* Streaming assistant message (in progress) */}
          {(streamingText || toolStatus) && (
            <div className="flex gap-2">
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center">
                <Bot className="h-3.5 w-3.5 text-primary" />
              </div>
              <div className="max-w-[85%]">
                {toolStatus && !streamingText && (
                  <Card>
                    <CardContent className="p-2.5">
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        {toolStatus}
                      </div>
                    </CardContent>
                  </Card>
                )}
                {streamingText && (
                  <Card>
                    <CardContent className="p-2.5">
                      <p className="text-xs whitespace-pre-wrap leading-relaxed">
                        {streamingText}
                        <span className="inline-block w-1.5 h-3.5 bg-primary/50 ml-0.5 animate-pulse" />
                      </p>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          )}

          {/* Loading state when no streaming has started */}
          {loading && !streamingText && !toolStatus && (
            <div className="flex gap-2">
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center">
                <Bot className="h-3.5 w-3.5 text-primary" />
              </div>
              <Card>
                <CardContent className="p-2.5">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Connecting...
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      <div className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && void handleSend()}
          placeholder={placeholder}
          disabled={loading}
          className="flex-1 text-xs h-8"
        />
        <Button
          size="sm"
          onClick={() => void handleSend()}
          disabled={loading || !input.trim()}
          aria-label="Send message"
          className="h-8 w-8 p-0"
        >
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Send className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>
    </div>
  );
}
