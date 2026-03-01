"use client";

import { useEffect, useState } from "react";
import { listCollections, createCollection, addToCollection } from "@/lib/api";
import type { CollectionResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Bookmark, Plus, Check } from "lucide-react";

interface SaveToCollectionProps {
  billId: string;
}

export function SaveToCollection({ billId }: SaveToCollectionProps) {
  const [collections, setCollections] = useState<CollectionResponse[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    listCollections().then((data) => setCollections(data.data)).catch(() => {});
  }, []);

  async function handleAdd(collectionId: number) {
    try {
      await addToCollection(collectionId, billId);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // 409 = already exists, that's fine
    }
  }

  async function handleCreateAndAdd() {
    const name = prompt("Collection name:");
    if (!name) return;
    try {
      const c = await createCollection(name);
      await addToCollection(c.id, billId);
      setCollections((prev) => [...prev, c]);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // silently fail
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          {saved ? (
            <Check className="mr-1.5 h-4 w-4 text-green-600" />
          ) : (
            <Bookmark className="mr-1.5 h-4 w-4" />
          )}
          {saved ? "Saved" : "Save"}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        {collections.map((c) => (
          <DropdownMenuItem key={c.id} onClick={() => handleAdd(c.id)}>
            {c.name}
          </DropdownMenuItem>
        ))}
        {collections.length > 0 && <DropdownMenuSeparator />}
        <DropdownMenuItem onClick={handleCreateAndAdd}>
          <Plus className="mr-1.5 h-4 w-4" />
          New collection...
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
