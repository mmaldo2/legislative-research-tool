"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getCollection } from "@/lib/api";
import type { CollectionDetailResponse } from "@/types/api";

export function SearchContextBanner({ collectionId }: { collectionId?: number }) {
  const [collection, setCollection] = useState<CollectionDetailResponse | null>(null);

  useEffect(() => {
    if (!collectionId || Number.isNaN(collectionId)) return;
    void getCollection(collectionId)
      .then(setCollection)
      .catch(() => setCollection(null));
  }, [collectionId]);

  if (!collectionId || Number.isNaN(collectionId) || !collection) return null;

  return (
    <div className="mb-6 rounded-lg border bg-muted/20 p-4 text-sm">
      <p className="font-medium">Searching for the active investigation: {collection.name}</p>
      <p className="mt-1 text-muted-foreground">
        Add relevant bills back into this working set and then continue into comparison,
        assistant, or memo generation.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link href={`/collections/${collection.id}`} className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent">
          Back to Investigation
        </Link>
        <Link href={`/assistant?collection_id=${collection.id}`} className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent">
          Ask Assistant
        </Link>
      </div>
    </div>
  );
}
