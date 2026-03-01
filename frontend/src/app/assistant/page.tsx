"use client";

import { useState, useRef, useEffect } from "react";
import { sendChatMessage } from "@/lib/api";
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

export default function AssistantPage() {
  const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
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
      const res = await sendChatMessage(text, conversationId);
      setConversationId(res.conversation_id);
      setMessages((prev) => [...prev, res.message]);
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
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 flex flex-col" style={{ height: "calc(100vh - 8rem)" }}>
      <h1 className="text-2xl font-bold mb-4">Research Assistant</h1>
      <p className="text-sm text-muted-foreground mb-4">
        Ask questions about legislation across all 50 states and Congress.
        I can search bills, analyze provisions, and compare legislation across jurisdictions.
      </p>

      {/* Messages area */}
      <ScrollArea className="flex-1 rounded-lg border p-4 mb-4">
        <div className="space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-12 text-muted-foreground">
              <Bot className="mx-auto h-12 w-12 mb-4 opacity-50" />
              <p className="text-sm">
                Try asking: &ldquo;What states have introduced data privacy bills this session?&rdquo;
              </p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
              {msg.role === "assistant" && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
              )}
              <div className={`max-w-[80%] ${msg.role === "user" ? "order-first" : ""}`}>
                <Card className={msg.role === "user" ? "bg-primary text-primary-foreground" : ""}>
                  <CardContent className="p-3">
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  </CardContent>
                </Card>
                {/* Tool calls */}
                {msg.tool_calls && msg.tool_calls.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {msg.tool_calls.map((tc, j) => (
                      <Badge key={j} variant="outline" className="text-xs gap-1">
                        {TOOL_ICONS[tc.tool_name] ?? <Search className="h-3 w-3" />}
                        {tc.tool_name.replace(/_/g, " ")}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
              {msg.role === "user" && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                  <User className="h-4 w-4" />
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                <Bot className="h-4 w-4 text-primary" />
              </div>
              <Card>
                <CardContent className="p-3">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </CardContent>
              </Card>
            </div>
          )}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      {/* Input bar */}
      <div className="flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="Ask about legislation..."
          disabled={loading}
          className="flex-1"
        />
        <Button onClick={handleSend} disabled={loading || !input.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}
