"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { getCollection } from "@/lib/api";
import type { CollectionDetailResponse } from "@/types/api";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function CompareClientPage({ collectionIdParam }: { collectionIdParam?: string }) {
  const collectionId = collectionIdParam ? parseInt(collectionIdParam, 10) : NaN;
  const hasCollectionContext = Number.isFinite(collectionId);
  const [collection, setCollection] = useState<CollectionDetailResponse | null>(null);
  const [billA, setBillA] = useState("");
  const [billB, setBillB] = useState("");

  useEffect(() => {
    if (!hasCollectionContext) return;
    void getCollection(collectionId)
      .then((data) => {
        setCollection(data);
        if (data.items[0]) setBillA(data.items[0].bill_id);
        if (data.items[1]) setBillB(data.items[1].bill_id);
      })
      .catch(() => setCollection(null));
  }, [hasCollectionContext, collectionId]);

  const compareHref = useMemo(() => {
    if (!billA || !billB) return "#";
    return `/compare?a=${encodeURIComponent(billA)}&b=${encodeURIComponent(billB)}${hasCollectionContext ? `&collection_id=${collectionId}` : ""}`;
  }, [billA, billB, hasCollectionContext, collectionId]);

  if (collection) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="mb-2 text-2xl font-bold">Compare Bills</h1>
        <p className="mb-6 text-muted-foreground">
          Choose two bills from the active investigation “{collection.name}” to compare.
        </p>
        <Card>
          <CardHeader>
            <CardTitle>Select bills from the working set</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Select value={billA} onValueChange={setBillA}>
              <SelectTrigger>
                <SelectValue placeholder="Choose first bill" />
              </SelectTrigger>
              <SelectContent>
                {collection.items.map((item) => (
                  <SelectItem key={item.id} value={item.bill_id}>
                    {item.bill_identifier || item.bill_id} — {item.bill_title || item.bill_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={billB} onValueChange={setBillB}>
              <SelectTrigger>
                <SelectValue placeholder="Choose second bill" />
              </SelectTrigger>
              <SelectContent>
                {collection.items.map((item) => (
                  <SelectItem key={item.id} value={item.bill_id} disabled={item.bill_id === billA}>
                    {item.bill_identifier || item.bill_id} — {item.bill_title || item.bill_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex flex-wrap gap-2">
              <Button asChild disabled={!billA || !billB || billA === billB}>
                <Link href={compareHref}>Compare Selected Bills</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href={`/collections/${collection.id}`}>Back to Investigation</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-4 text-2xl font-bold">Compare Bills</h1>
      <p className="text-muted-foreground">
        Select two bills to compare. Use the Similar Bills tab on any bill detail page or start from an investigation with at least two saved bills.
      </p>
    </div>
  );
}
