import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SaveToCollection } from "@/components/save-to-collection";
import { formatJurisdiction, formatStatus, statusVariant, truncate } from "@/lib/format";

interface BillCardProps {
  id: string;
  identifier: string;
  title: string;
  jurisdictionId: string;
  status: string | null;
  score?: number;
  snippet?: string | null;
  collectionId?: number;
}

export function BillCard({
  id,
  identifier,
  title,
  jurisdictionId,
  status,
  score,
  snippet,
  collectionId,
}: BillCardProps) {
  const href = collectionId
    ? `/bills/${encodeURIComponent(id)}?collection_id=${collectionId}`
    : `/bills/${encodeURIComponent(id)}`;

  return (
    <Card className="transition-colors hover:bg-accent/50">
      <CardHeader className="gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className="font-mono text-xs">
            {identifier}
          </Badge>
          <Badge variant="secondary" className="text-xs">
            {formatJurisdiction(jurisdictionId)}
          </Badge>
          {status && (
            <Badge variant={statusVariant(status)} className="text-xs">
              {formatStatus(status)}
            </Badge>
          )}
          {score !== undefined && (
            <span className="ml-auto text-xs text-muted-foreground">
              {(score * 100).toFixed(0)}% match
            </span>
          )}
        </div>
        <div className="space-y-2">
          <CardTitle className="text-base leading-snug">
            <Link href={href} className="hover:underline">
              {truncate(title, 200)}
            </Link>
          </CardTitle>
          {snippet && (
            <CardDescription className="text-sm">
              {truncate(snippet, 300)}
            </CardDescription>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline" size="sm">
            <Link href={href}>Open bill</Link>
          </Button>
          <SaveToCollection billId={id} collectionId={collectionId} compact />
        </div>
      </CardHeader>
    </Card>
  );
}
