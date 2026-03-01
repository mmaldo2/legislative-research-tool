import { Suspense } from "react";
import type { Metadata } from "next";
import { SearchForm } from "./search-form";
import { SearchResults } from "./search-results";

export const metadata: Metadata = {
  title: "Search Bills | Legislative Research Tool",
};

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const q = typeof params.q === "string" ? params.q : "";
  const jurisdiction =
    typeof params.jurisdiction === "string" ? params.jurisdiction : "";
  const mode = typeof params.mode === "string" ? params.mode : "hybrid";
  const page = typeof params.page === "string" ? parseInt(params.page, 10) : 1;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold">Search Bills</h1>
      <SearchForm
        defaultQuery={q}
        defaultJurisdiction={jurisdiction}
        defaultMode={mode}
      />

      {q && (
        <Suspense
          key={`${q}-${jurisdiction}-${mode}-${page}`}
          fallback={<SearchResultsSkeleton />}
        >
          <SearchResults
            q={q}
            jurisdiction={jurisdiction || undefined}
            mode={mode as "keyword" | "semantic" | "hybrid"}
            page={page}
          />
        </Suspense>
      )}

      {!q && (
        <p className="mt-12 text-center text-muted-foreground">
          Enter a search query to find bills across all jurisdictions.
        </p>
      )}
    </div>
  );
}

function SearchResultsSkeleton() {
  return (
    <div className="mt-6 space-y-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="h-24 animate-pulse rounded-lg border bg-muted/30"
        />
      ))}
    </div>
  );
}
