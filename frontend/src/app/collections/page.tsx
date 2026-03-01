"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listCollections, createCollection, deleteCollection } from "@/lib/api";
import type { CollectionResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Plus, Trash2, FolderOpen } from "lucide-react";

export default function CollectionsPage() {
  const [collections, setCollections] = useState<CollectionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await listCollections();
      setCollections(data.data);
      setError(null);
    } catch (e) {
      console.error("Failed to load collections:", e);
      setError("Failed to load collections.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await createCollection(newName.trim());
      setNewName("");
      await load();
    } catch (e) {
      console.error("Failed to create collection:", e);
      setError("Failed to create collection.");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteCollection(id);
      await load();
    } catch (e) {
      console.error("Failed to delete collection:", e);
      setError("Failed to delete collection.");
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">Research Collections</h1>
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-lg bg-muted/30" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Research Collections</h1>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Create new collection */}
      <div className="flex gap-2 mb-6">
        <Input
          placeholder="New collection name..."
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          className="max-w-sm"
        />
        <Button onClick={handleCreate} disabled={creating || !newName.trim()}>
          <Plus className="mr-1.5 h-4 w-4" />
          Create
        </Button>
      </div>

      {collections.length === 0 ? (
        <div className="text-center py-12">
          <FolderOpen className="mx-auto h-12 w-12 text-muted-foreground/50 mb-4" />
          <p className="text-muted-foreground">
            No collections yet. Create one to start saving bills for your research.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {collections.map((c) => (
            <Card key={c.id} className="transition-colors hover:bg-accent/50">
              <CardHeader className="flex-row items-center justify-between gap-4">
                <Link href={`/collections/${c.id}`} className="flex-1">
                  <CardTitle className="text-base">{c.name}</CardTitle>
                  {c.description && (
                    <p className="text-sm text-muted-foreground mt-1">{c.description}</p>
                  )}
                </Link>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{c.item_count} bills</Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(c.id)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
