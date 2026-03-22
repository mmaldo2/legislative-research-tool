"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  sendChatMessage,
  sendWorkspaceChatMessage,
  getWorkspaceConversations,
} from "@/lib/api";
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
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load existing workspace conversation on mount
  useEffect(() => {
    if (!workspaceId || initialLoaded) return;
    setInitialLoaded(true);

    void (async () => {
      try {
        const data = await getWorkspaceConversations(workspaceId);
        if (data.conversations.length > 0) {
          setConversationId(data.conversations[0].id);
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

    try {
      const res = workspaceId
        ? await sendWorkspaceChatMessage(workspaceId, text, conversationId)
        : await sendChatMessage(text, conversationId);
      setConversationId(res.conversation_id);
      setMessages((prev) => [...prev, res.message]);

      // Check for suggestion blockquotes
      if (onSuggestion && res.message.content) {
        const idx = res.message.content.indexOf("> Suggested language:");
        if (idx !== -1) {
          const rest = res.message.content.slice(idx + "> Suggested language:".length);
          const endIdx = rest.indexOf("\n\n");
          const suggested = endIdx !== -1 ? rest.slice(0, endIdx) : rest;
          onSuggestion(suggested.trim());
        }
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again.",
          tool_calls: null,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, workspaceId, conversationId, onSuggestion]);

  const defaultEmpty = workspaceId
    ? "Ask questions about your draft, precedent bills, or legislative research."
    : 'Try asking: "What states have introduced data privacy bills?"';

  return (
    <div className={`flex flex-col ${className}`}>
      <ScrollArea className="flex-1 rounded-lg border p-3 mb-3">
        <div className="space-y-3">
          {messages.length === 0 && (
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
          {loading && (
            <div className="flex gap-2">
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center">
                <Bot className="h-3.5 w-3.5 text-primary" />
              </div>
              <Card>
                <CardContent className="p-2.5">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Researching...
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
