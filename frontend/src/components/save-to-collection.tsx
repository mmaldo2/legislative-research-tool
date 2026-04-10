"use client";

import { useEffect, useState } from "react";
import { listCollections, createCollection, addToCollection } from "@/lib/api";
import type { CollectionResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  collectionId?: number;
  compact?: boolean;
}

export function SaveToCollection({ billId, collectionId, compact = false }: SaveToCollectionProps) {
  const [collections, setCollections] = useState<CollectionResponse[]>([]);
  const [saved, setSaved] = useState(false);
  const [showNewInput, setShowNewInput] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    listCollections()
      .then((data) => setCollections(data.data))
      .catch((e) => console.error("Failed to load collections:", e));
  }, []);

  async function handleAdd(collectionId: number) {
    try {
      await addToCollection(collectionId, billId);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      const error = e as { status?: number } | undefined;
      if (error?.status === 409) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
        return;
      }
      console.error("Failed to add to collection:", e);
    }
  }

  async function handleCreateAndAdd() {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const c = await createCollection(newName.trim());
      await addToCollection(c.id, billId);
      setCollections((prev) => [...prev, c]);
      setSaved(true);
      setNewName("");
      setShowNewInput(false);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error("Failed to create collection:", e);
    } finally {
      setCreating(false);
    }
  }

  if (collectionId) {
    return (
      <Button
        type="button"
        variant={saved ? "secondary" : "outline"}
        size={compact ? "sm" : "sm"}
        onClick={() => handleAdd(collectionId)}
      >
        {saved ? (
          <Check className="mr-1.5 h-4 w-4 text-green-600" />
        ) : (
          <Bookmark className="mr-1.5 h-4 w-4" />
        )}
        {saved ? "Added" : compact ? "Add" : "Add to Investigation"}
      </Button>
    );
  }

  return (
    <DropdownMenu onOpenChange={(open) => { if (!open) setShowNewInput(false); }}>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          {saved ? (
            <Check className="mr-1.5 h-4 w-4 text-green-600" />
          ) : (
            <Bookmark className="mr-1.5 h-4 w-4" />
          )}
          {saved ? "Added" : "Add to Investigation"}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        {collections.map((c) => (
          <DropdownMenuItem key={c.id} onClick={() => handleAdd(c.id)}>
            {c.name}
          </DropdownMenuItem>
        ))}
        {collections.length > 0 && <DropdownMenuSeparator />}
        {showNewInput ? (
          <div className="flex gap-1 p-1" onClick={(e) => e.stopPropagation()}>
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreateAndAdd()}
              placeholder="Investigation name..."
              className="h-8 text-sm"
              autoFocus
            />
            <Button
              size="sm"
              className="h-8"
              onClick={handleCreateAndAdd}
              disabled={creating || !newName.trim()}
            >
              Add
            </Button>
          </div>
        ) : (
          <DropdownMenuItem onClick={() => setShowNewInput(true)}>
            <Plus className="mr-1.5 h-4 w-4" />
            New investigation...
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
