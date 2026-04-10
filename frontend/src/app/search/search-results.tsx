import { searchBills } from "@/lib/api";
import { ApiErrorBanner } from "@/components/api-error";
import { BillCard } from "@/components/bill-card";
import { Pagination } from "@/components/pagination";

interface SearchResultsProps {
  q: string;
  jurisdiction?: string;
  mode: "keyword" | "semantic" | "hybrid";
  page: number;
  collectionId?: number;
}

export async function SearchResults({
  q,
  jurisdiction,
  mode,
  page,
  collectionId,
}: SearchResultsProps) {
  let data;
  try {
    data = await searchBills({ q, jurisdiction, mode, page, per_page: 20 });
  } catch {
    return (
      <ApiErrorBanner
        message="Failed to fetch search results. Make sure the API server is running."
        className="mt-6"
      />
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
            jurisdictionId={result.jurisdiction_id}
            status={result.status}
            score={result.score}
            snippet={result.snippet}
            collectionId={collectionId}
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
