"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { getCollection, removeFromCollection, updateCollectionItemNotes } from "@/lib/api";
import type { CollectionDetailResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Trash2, Save } from "lucide-react";

export default function CollectionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const collectionId = parseInt(id, 10);
  const [collection, setCollection] = useState<CollectionDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingNotes, setEditingNotes] = useState<Record<string, string>>({});

  async function load() {
    try {
      const data = await getCollection(collectionId);
      setCollection(data);
    } catch {
      // handle error
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [collectionId]);

  async function handleRemove(billId: string) {
    await removeFromCollection(collectionId, billId);
    await load();
  }

  async function handleSaveNotes(billId: string) {
    const notes = editingNotes[billId];
    if (notes === undefined) return;
    await updateCollectionItemNotes(collectionId, billId, notes || null);
    setEditingNotes((prev) => {
      const next = { ...prev };
      delete next[billId];
      return next;
    });
    await load();
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div className="h-8 w-64 animate-pulse rounded bg-muted/30 mb-6" />
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-muted/30" />
          ))}
        </div>
      </div>
    );
  }

  if (!collection) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <p className="text-muted-foreground">Collection not found.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <Link href="/collections" className="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4">
        <ArrowLeft className="h-4 w-4" />
        Back to collections
      </Link>
      <h1 className="text-2xl font-bold mb-2">{collection.name}</h1>
      {collection.description && (
        <p className="text-muted-foreground mb-6">{collection.description}</p>
      )}

      {collection.items.length === 0 ? (
        <p className="text-muted-foreground text-center py-8">
          No bills in this collection yet. Use the search to find and add bills.
        </p>
      ) : (
        <div className="space-y-3">
          {collection.items.map((item) => (
            <Card key={item.id}>
              <CardHeader className="flex-row items-start justify-between gap-4">
                <div className="flex-1">
                  <Link href={`/bills/${encodeURIComponent(item.bill_id)}`}>
                    <CardTitle className="text-base hover:underline">
                      {item.bill_id}
                    </CardTitle>
                  </Link>
                  {/* Notes */}
                  {editingNotes[item.bill_id] !== undefined ? (
                    <div className="flex gap-2 mt-2">
                      <Input
                        value={editingNotes[item.bill_id]}
                        onChange={(e) =>
                          setEditingNotes((prev) => ({
                            ...prev,
                            [item.bill_id]: e.target.value,
                          }))
                        }
                        placeholder="Add research notes..."
                        className="text-sm"
                      />
                      <Button size="sm" onClick={() => handleSaveNotes(item.bill_id)}>
                        <Save className="h-3 w-3" />
                      </Button>
                    </div>
                  ) : (
                    <p
                      className="text-sm text-muted-foreground mt-1 cursor-pointer hover:text-foreground"
                      onClick={() =>
                        setEditingNotes((prev) => ({
                          ...prev,
                          [item.bill_id]: item.notes || "",
                        }))
                      }
                    >
                      {item.notes || "Click to add notes..."}
                    </p>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRemove(item.bill_id)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
