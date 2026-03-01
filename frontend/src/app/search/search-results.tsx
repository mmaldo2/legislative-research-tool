import { searchBills } from "@/lib/api";
import { BillCard } from "@/components/bill-card";
import { Pagination } from "@/components/pagination";

interface SearchResultsProps {
  q: string;
  jurisdiction?: string;
  mode: "keyword" | "semantic" | "hybrid";
  page: number;
}

export async function SearchResults({
  q,
  jurisdiction,
  mode,
  page,
}: SearchResultsProps) {
  let data;
  try {
    data = await searchBills({ q, jurisdiction, mode, page, per_page: 20 });
  } catch {
    return (
      <div className="mt-6 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
        Failed to fetch search results. Make sure the API server is running at{" "}
        <code className="font-mono">{process.env.NEXT_PUBLIC_API_URL}</code>.
      </div>
    );
  }

  if (data.data.length === 0) {
    return (
      <p className="mt-8 text-center text-muted-foreground">
        No results found for &ldquo;{q}&rdquo;.
      </p>
    );
  }

  return (
    <div className="mt-6">
      <div className="space-y-3">
        {data.data.map((result) => (
          <BillCard
            key={result.bill_id}
            id={result.bill_id}
            identifier={result.identifier}
            title={result.title}
            jurisdiction_id={result.jurisdiction_id}
            status={result.status}
            score={result.score}
            snippet={result.snippet}
          />
        ))}
      </div>

      <Pagination
        page={data.meta.page ?? page}
        perPage={data.meta.per_page ?? 20}
        totalCount={data.meta.total_count ?? 0}
      />
    </div>
  );
}
