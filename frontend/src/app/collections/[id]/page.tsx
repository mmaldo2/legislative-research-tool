"use client";

import { useCallback, useEffect, useState, use } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getCollection, removeFromCollection, updateCollectionItemNotes } from "@/lib/api";
import type { CollectionDetailResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ArrowLeft, Trash2, Save } from "lucide-react";

export default function CollectionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const collectionId = parseInt(id, 10);
  if (Number.isNaN(collectionId)) {
    notFound();
  }

  const [collection, setCollection] = useState<CollectionDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingNotes, setEditingNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await getCollection(collectionId);
      setCollection(data);
      setError(null);
    } catch (e) {
      console.error("Failed to load collection:", e);
      setError("Failed to load collection.");
    } finally {
      setLoading(false);
    }
  }, [collectionId]);

  useEffect(() => { load(); }, [load]);

  async function handleRemove(billId: string) {
    try {
      await removeFromCollection(collectionId, billId);
      await load();
    } catch (e) {
      console.error("Failed to remove item:", e);
      setError("Failed to remove item from collection.");
    }
  }

  async function handleSaveNotes(billId: string) {
    const notes = editingNotes[billId];
    if (notes === undefined) return;
    try {
      await updateCollectionItemNotes(collectionId, billId, notes || null);
      setEditingNotes((prev) => {
        const next = { ...prev };
        delete next[billId];
        return next;
      });
      await load();
    } catch (e) {
      console.error("Failed to save notes:", e);
      setError("Failed to save notes.");
    }
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
        Back to investigations
      </Link>
      <h1 className="text-2xl font-bold mb-2">{collection.name}</h1>
      <p className="mb-2 text-sm font-medium text-muted-foreground">Investigation workspace</p>
      {collection.description ? (
        <p className="text-muted-foreground mb-4">{collection.description}</p>
      ) : (
        <p className="text-muted-foreground mb-4">No investigation summary yet.</p>
      )}
      <div className="mb-6 rounded-lg border bg-muted/20 p-4">
        <p className="text-sm text-foreground">
          Use this investigation to track a policy question, save the most relevant bills,
          and move from discovery into comparison, notes, and deeper research.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="rounded-full border px-2 py-1">Working set: {collection.items.length} bill{collection.items.length === 1 ? "" : "s"}</span>
          <span className="rounded-full border px-2 py-1">Question → compare → synthesize</span>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link href={`/search?collection_id=${collectionId}`} className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent">
            Continue Search
          </Link>
          <Link href={`/assistant?collection_id=${collectionId}`} className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent">
            Ask Assistant
          </Link>
          {collection.items.length >= 2 && (
            <Link href={`/compare?collection_id=${collectionId}`} className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent">
              Compare Bills
            </Link>
          )}
          <Link href={`/reports?collection_id=${collectionId}`} className="inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent">
            Generate Memo
          </Link>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="mb-6 rounded-lg border p-4 text-sm">
        <p className="font-medium">Suggested next step</p>
        {collection.items.length === 0 ? (
          <p className="mt-1 text-muted-foreground">
            Start by adding 2-5 relevant bills from search so this investigation has a usable working set.
          </p>
        ) : collection.items.length === 1 ? (
          <p className="mt-1 text-muted-foreground">
            You have one bill saved. Add at least one more related bill so you can compare approaches and ask stronger investigation questions.
          </p>
        ) : (
          <p className="mt-1 text-muted-foreground">
            Compare <span className="font-medium text-foreground">{collection.items[0].bill_identifier || collection.items[0].bill_id}</span> with <span className="font-medium text-foreground">{collection.items[1].bill_identifier || collection.items[1].bill_id}</span> or ask the assistant for the biggest differences across the current working set.
          </p>
        )}
      </div>

      {collection.items.length === 0 ? (
        <div className="py-8 text-center">
          <p className="text-muted-foreground">
            No bills in this investigation yet. Use search to find relevant bills and
            build your working set.
          </p>
          <Link
            href={`/search?collection_id=${collectionId}`}
            className="mt-4 inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent"
          >
            Go to Search
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {collection.items.map((item) => (
            <Card key={item.id}>
              <CardHeader className="flex-row items-start justify-between gap-4">
                <div className="flex-1">
                  <Link href={`/bills/${encodeURIComponent(item.bill_id)}?collection_id=${collectionId}`}>
                    <CardTitle className="text-base hover:underline">
                      {item.bill_identifier || item.bill_id}
                    </CardTitle>
                  </Link>
                  {(item.bill_title || item.jurisdiction_id || item.status) && (
                    <p className="mt-1 text-sm text-muted-foreground">
                      {item.bill_title || item.bill_id}
                      {item.jurisdiction_id ? ` • ${item.jurisdiction_id}` : ""}
                      {item.status ? ` • ${item.status}` : ""}
                    </p>
                  )}
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
                      <Button
                        size="sm"
                        onClick={() => handleSaveNotes(item.bill_id)}
                        aria-label="Save notes"
                      >
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
                  aria-label={`Remove ${item.bill_id} from collection`}
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
