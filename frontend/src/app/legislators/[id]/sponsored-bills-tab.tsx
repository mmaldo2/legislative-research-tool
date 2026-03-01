import { listBills } from "@/lib/api";
import { BillCard } from "@/components/bill-card";
import { ApiErrorBanner } from "@/components/api-error";

interface SponsoredBillsTabProps {
  personId: string;
}

export async function SponsoredBillsTab({ personId }: SponsoredBillsTabProps) {
  let bills;

  try {
    bills = await listBills({ sponsor: personId, per_page: 20 });
  } catch {
    return (
      <ApiErrorBanner message="Failed to load sponsored bills. Please try again later." />
    );
  }

  if (bills.data.length === 0) {
    return (
      <p className="text-muted-foreground">
        No sponsored bills found for this legislator.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {bills.data.map((bill) => (
        <BillCard
          key={bill.id}
          id={bill.id}
          identifier={bill.identifier}
          title={bill.title}
          jurisdictionId={bill.jurisdiction_id}
          status={bill.status}
        />
      ))}
    </div>
  );
}
