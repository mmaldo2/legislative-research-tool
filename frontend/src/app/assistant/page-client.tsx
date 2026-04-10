"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ChatPanel } from "@/components/chat-panel";
import { getCollection } from "@/lib/api";
import type { CollectionDetailResponse } from "@/types/api";

export default function AssistantClientPage() {
  const searchParams = useSearchParams();
  const collectionIdParam = searchParams.get("collection_id");
  const collectionId = collectionIdParam ? parseInt(collectionIdParam, 10) : NaN;
  const hasCollectionContext = Number.isFinite(collectionId);
  const [collection, setCollection] = useState<CollectionDetailResponse | null>(null);

  useEffect(() => {
    if (!hasCollectionContext) return;
    void getCollection(collectionId)
      .then(setCollection)
      .catch(() => setCollection(null));
  }, [hasCollectionContext, collectionId]);

  const activeCollection = hasCollectionContext ? collection : null;

  const contextPrefix = useMemo(() => {
    if (!activeCollection) return undefined;
    const billList = activeCollection.items.slice(0, 12).map((item) => item.bill_id).join(", ");
    const notes = activeCollection.items
      .filter((item) => item.notes)
      .slice(0, 5)
      .map((item) => `${item.bill_id}: ${item.notes}`)
      .join("\n");
    return [
      `Active investigation: ${activeCollection.name}`,
      activeCollection.description ? `Summary: ${activeCollection.description}` : undefined,
      `Bills in working set: ${billList || "none"}`,
      notes ? `Investigation notes:\n${notes}` : undefined,
      "Use this investigation context when answering. Prefer reasoning over the active working set before broadening to the full corpus.",
    ].filter(Boolean).join("\n");
  }, [activeCollection]);

  const intro = activeCollection
    ? `Working inside the investigation \"${activeCollection.name}\". The assistant should prioritize the current working set and only broaden to the full corpus when needed.`
    : "Ask questions about legislation across all 50 states and Congress. The assistant can search bills, analyze provisions, and compare legislation across jurisdictions.";

  const empty = activeCollection
    ? `Try asking: \"What are the biggest differences across the bills in ${activeCollection.name}?\"`
    : 'Try asking: "What states have introduced data privacy bills this session?"';

  return (
    <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-3xl flex-col px-4 py-8">
      <h1 className="mb-4 text-2xl font-bold">Research Assistant</h1>
      <p className="mb-4 text-sm text-muted-foreground">{intro}</p>
      {activeCollection && (
        <div className="mb-4 rounded-lg border bg-muted/20 p-3 text-sm">
          <p className="font-medium">Active investigation: {activeCollection.name}</p>
          <p className="mt-1 text-muted-foreground">
            Working set: {activeCollection.items.length} bill{activeCollection.items.length === 1 ? "" : "s"}
          </p>
        </div>
      )}
      <ChatPanel
        className="flex-1"
        placeholder={activeCollection ? "Ask about this investigation..." : "Ask about legislation..."}
        emptyMessage={empty}
        contextPrefix={contextPrefix}
      />
    </div>
  );
}
