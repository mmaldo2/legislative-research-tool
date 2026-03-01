import { Suspense } from "react";
import type { Metadata } from "next";
import { LegislatorsList } from "./legislators-list";

export const metadata: Metadata = {
  title: "Legislators | Legislative Research Tool",
};

export default async function LegislatorsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const jurisdiction =
    typeof params.jurisdiction === "string" ? params.jurisdiction : "";
  const party = typeof params.party === "string" ? params.party : "";
  const chamber = typeof params.chamber === "string" ? params.chamber : "";
  const q = typeof params.q === "string" ? params.q : "";
  const page = typeof params.page === "string" ? parseInt(params.page, 10) : 1;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold">Legislators</h1>
      <Suspense
        key={`${jurisdiction}-${party}-${chamber}-${q}-${page}`}
        fallback={<ListSkeleton />}
      >
        <LegislatorsList
          jurisdiction={jurisdiction || undefined}
          party={party || undefined}
          chamber={chamber || undefined}
          q={q || undefined}
          page={page}
        />
      </Suspense>
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 10 }).map((_, i) => (
        <div
          key={i}
          className="h-16 animate-pulse rounded-lg border bg-muted/30"
        />
      ))}
    </div>
  );
}
