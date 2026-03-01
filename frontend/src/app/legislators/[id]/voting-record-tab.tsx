import Link from "next/link";
import { getPersonVotes } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ApiErrorBanner } from "@/components/api-error";
import { formatChamber, truncate } from "@/lib/format";

interface VotingRecordTabProps {
  personId: string;
}

function voteOptionVariant(
  option: string,
): "default" | "destructive" | "secondary" {
  const lower = option.toLowerCase();
  if (lower === "yes" || lower === "yea") return "default";
  if (lower === "no" || lower === "nay") return "destructive";
  return "secondary";
}

export async function VotingRecordTab({ personId }: VotingRecordTabProps) {
  let votes;

  try {
    votes = await getPersonVotes(personId, { per_page: 50 });
  } catch {
    return (
      <ApiErrorBanner message="Failed to load voting records. Please try again later." />
    );
  }

  if (votes.data.length === 0) {
    return (
      <p className="text-muted-foreground">
        No voting records available.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {votes.data.map((vote) => (
        <Card key={vote.vote_event_id}>
          <CardContent className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:gap-4">
            {/* Bill info */}
            <div className="flex-1 min-w-0">
              <Link
                href={`/bills/${encodeURIComponent(vote.bill_id)}`}
                className="font-mono text-sm font-medium text-primary hover:underline"
              >
                {vote.bill_identifier}
              </Link>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {truncate(vote.bill_title, 120)}
              </p>
            </div>

            {/* Metadata badges */}
            <div className="flex flex-wrap items-center gap-2 shrink-0">
              {vote.vote_date && (
                <span className="text-xs text-muted-foreground">
                  {vote.vote_date}
                </span>
              )}
              {vote.chamber && (
                <Badge variant="secondary" className="text-xs">
                  {formatChamber(vote.chamber)}
                </Badge>
              )}
              <Badge variant={voteOptionVariant(vote.option)} className="text-xs">
                {vote.option}
              </Badge>
              {vote.result && (
                <Badge variant="outline" className="text-xs">
                  {vote.result}
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
