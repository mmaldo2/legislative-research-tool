"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { listBillHearings } from "@/lib/api";
import type { HearingResponse } from "@/types/api";

interface HearingsTabProps {
  billId: string;
}

const chamberLabel = (chamber: string | null) => {
  if (!chamber) return null;
  const labels: Record<string, string> = {
    senate: "Senate",
    house: "House",
    joint: "Joint",
  };
  return labels[chamber] ?? chamber;
};

const chamberVariant = (chamber: string | null) => {
  if (chamber === "senate") return "default" as const;
  if (chamber === "house") return "secondary" as const;
  return "outline" as const;
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "Date TBD";
  try {
    return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function HearingsTab({ billId }: HearingsTabProps) {
  const [hearings, setHearings] = useState<HearingResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchHearings() {
      setLoading(true);
      setError(null);
      try {
        const response = await listBillHearings(billId);
        if (!cancelled) {
          setHearings(response.data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load hearings");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchHearings();
    return () => {
      cancelled = true;
    };
  }, [billId]);

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-lg border bg-muted/30" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      </div>
    );
  }

  if (hearings.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-muted-foreground">
          No committee hearings have been linked to this bill yet.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4" aria-live="polite">
      <p className="text-sm text-muted-foreground">
        {hearings.length} hearing{hearings.length !== 1 ? "s" : ""} found
      </p>

      {hearings.map((hearing) => (
        <Card key={hearing.id}>
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-2">
              <CardTitle className="text-base leading-snug">
                {hearing.title}
              </CardTitle>
              <div className="flex shrink-0 items-center gap-1.5">
                {hearing.chamber && (
                  <Badge variant={chamberVariant(hearing.chamber)} className="text-xs">
                    {chamberLabel(hearing.chamber)}
                  </Badge>
                )}
                {hearing.congress && (
                  <Badge variant="outline" className="text-xs">
                    {hearing.congress}th Congress
                  </Badge>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">
                {hearing.committee_name}
              </span>
              <span>{formatDate(hearing.hearing_date)}</span>
              {hearing.location && <span>{hearing.location}</span>}
            </div>
            {hearing.url && (
              <a
                href={hearing.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-block text-sm text-primary underline-offset-4 hover:underline"
              >
                View on Congress.gov
              </a>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
