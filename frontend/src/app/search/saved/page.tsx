"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, Trash2, Play, BookmarkPlus } from "lucide-react";
import { useSavedSearches } from "@/hooks/use-saved-searches";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function SavedSearchesPage() {
  const router = useRouter();
  const { searches, deleteSearch } = useSavedSearches();

  function handleRun(search: {
    query: string;
    jurisdiction: string;
    mode: string;
  }) {
    const params = new URLSearchParams();
    params.set("q", search.query);
    if (search.jurisdiction) params.set("jurisdiction", search.jurisdiction);
    if (search.mode && search.mode !== "hybrid")
      params.set("mode", search.mode);
    params.set("page", "1");
    router.push(`/search?${params.toString()}`);
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Saved Searches</h1>
        <Link
          href="/search"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <Search className="h-4 w-4" />
          Back to Search
        </Link>
      </div>

      {searches.length === 0 ? (
        <div className="mt-16 flex flex-col items-center gap-4 text-center">
          <BookmarkPlus className="h-12 w-12 text-muted-foreground/50" />
          <p className="text-muted-foreground">
            No saved searches yet. Run a search and click &quot;Save&quot; to
            add it here.
          </p>
          <Link href="/search">
            <Button variant="outline">
              <Search className="h-4 w-4" />
              Go to Search
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {searches.map((search) => (
            <Card key={search.id}>
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <CardTitle className="text-base">{search.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleRun(search)}
                    >
                      <Play className="h-3.5 w-3.5" />
                      Run
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteSearch(search.id)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col gap-3">
                  <code className="block rounded-md bg-muted px-3 py-2 text-sm">
                    {search.query}
                  </code>
                  <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                    {search.jurisdiction && (
                      <Badge variant="outline">{search.jurisdiction}</Badge>
                    )}
                    <Badge variant="secondary">{search.mode}</Badge>
                    <span className="ml-auto text-xs text-muted-foreground">
                      Saved {formatDate(search.createdAt)}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
