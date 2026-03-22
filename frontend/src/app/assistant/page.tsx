"use client";

import { ChatPanel } from "@/components/chat-panel";

export default function AssistantPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8 flex flex-col h-[calc(100vh-8rem)]">
      <h1 className="text-2xl font-bold mb-4">Research Assistant</h1>
      <p className="text-sm text-muted-foreground mb-4">
        Ask questions about legislation across all 50 states and Congress.
        The assistant can search bills, analyze provisions, and compare
        legislation across jurisdictions.
      </p>
      <ChatPanel
        className="flex-1"
        placeholder="Ask about legislation..."
        emptyMessage='Try asking: "What states have introduced data privacy bills this session?"'
      />
    </div>
  );
}
