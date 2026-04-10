"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAnalysis } from "@/hooks/use-analysis";
import { generateCollectionReport, generateReport, getCollection } from "@/lib/api";
import { formatJurisdiction } from "@/lib/format";
import type { CollectionDetailResponse, ReportOutput } from "@/types/api";

export default function ReportsClientPage() {
  const searchParams = useSearchParams();
  const collectionIdParam = searchParams.get("collection_id");
  const collectionId = collectionIdParam ? parseInt(collectionIdParam, 10) : NaN;
  const hasCollectionContext = Number.isFinite(collectionId);
  const [collection, setCollection] = useState<CollectionDetailResponse | null>(null);
  const [query, setQuery] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [submitted, setSubmitted] = useState<{
    query?: string;
    jurisdiction?: string;
    collectionId?: number;
  } | null>(null);

  useEffect(() => {
    if (!hasCollectionContext) return;
    void getCollection(collectionId)
      .then((data) => {
        setCollection(data);
        setQuery((current) => current || data.name);
      })
      .catch(() => setCollection(null));
  }, [hasCollectionContext, collectionId]);

  const activeCollection = hasCollectionContext ? collection : null;

  const fetcher = useCallback(
    (signal: AbortSignal) => {
      if (!submitted) return Promise.reject(new Error("No report request"));
      if (submitted.collectionId) {
        return generateCollectionReport(submitted.collectionId, signal);
      }
      return generateReport(
        submitted.query ?? "",
        submitted.jurisdiction || undefined,
        20,
        signal,
      );
    },
    [submitted],
  );

  const { result, loading, error, analyze } = useAnalysis<ReportOutput>(fetcher);

  useEffect(() => {
    if (submitted) {
      analyze();
    }
  }, [submitted, analyze]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (hasCollectionContext && activeCollection) {
      setSubmitted({ collectionId });
      return;
    }
    if (!query.trim() || query.trim().length < 3) return;
    setSubmitted({ query: query.trim(), jurisdiction: jurisdiction.trim() });
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Research Reports</h1>
        <p className="mt-1 text-muted-foreground">
          {activeCollection
            ? `Generate a memo from the active investigation \"${activeCollection.name}\" and its current working set.`
            : "Generate comprehensive policy research reports by searching across all jurisdictions."}
        </p>
      </div>

      <Card className="mb-6">
        <CardContent className="pt-6">
          {activeCollection ? (
            <div className="space-y-4">
              <div className="rounded-lg border bg-muted/20 p-4 text-sm">
                <p className="font-medium">Active investigation: {activeCollection.name}</p>
                <p className="mt-1 text-muted-foreground">
                  Using {activeCollection.items.length} bill{activeCollection.items.length === 1 ? "" : "s"} from the current working set.
                </p>
                {activeCollection.description && (
                  <p className="mt-2 text-muted-foreground">{activeCollection.description}</p>
                )}
              </div>
              <Button type="button" onClick={() => handleSubmit()} disabled={loading || activeCollection.items.length === 0}>
                {loading ? "Generating..." : "Generate Memo from Investigation"}
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
              <label className="sr-only" htmlFor="report-query">Research topic</label>
              <Input
                id="report-query"
                placeholder="e.g. gun control, minimum wage, housing..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="flex-1"
                minLength={3}
                required
              />
              <label className="sr-only" htmlFor="report-jurisdiction">Jurisdiction</label>
              <Input
                id="report-jurisdiction"
                placeholder="Jurisdiction (optional)"
                value={jurisdiction}
                onChange={(e) => setJurisdiction(e.target.value)}
                className="sm:w-48"
              />
              <Button type="submit" disabled={loading || query.trim().length < 3}>
                {loading ? "Generating..." : "Generate Report"}
              </Button>
            </form>
          )}
          {error && (
            <p className="mt-2 text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      {result && <ReportView report={result} collection={activeCollection} />}
    </div>
  );
}

function ReportView({ report, collection }: { report: ReportOutput; collection?: CollectionDetailResponse | null }) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{report.title}</CardTitle>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge variant="outline">
              {report.bills_analyzed} bill{report.bills_analyzed !== 1 && "s"} analyzed
            </Badge>
            <Badge variant="outline">
              {report.jurisdictions_covered.length} jurisdiction{report.jurisdictions_covered.length !== 1 && "s"}
            </Badge>
            <Badge variant="outline" className="text-xs">
              {(report.confidence * 100).toFixed(0)}% confidence
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <p className="leading-relaxed whitespace-pre-line">
            {report.executive_summary}
          </p>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-1">
        {report.jurisdictions_covered.map((j) => (
          <Badge key={j} variant="secondary" className="text-xs">
            {formatJurisdiction(j)}
          </Badge>
        ))}
      </div>

      {collection && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Evidence Used</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {collection.items.map((item) => (
                <li key={item.id}>
                  <a href={`/bills/${encodeURIComponent(item.bill_id)}?collection_id=${collection.id}`} className="font-medium text-primary hover:underline">
                    {item.bill_identifier || item.bill_id}
                  </a>
                  {item.bill_title ? ` — ${item.bill_title}` : ""}
                  {item.notes ? ` — ${item.notes}` : ""}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {report.sections.map((section, i) => (
        <Card key={i}>
          <CardHeader>
            <CardTitle className="text-lg">{section.heading}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="prose prose-sm max-w-none whitespace-pre-line dark:prose-invert">
              {section.content}
            </div>
          </CardContent>
        </Card>
      ))}

      {report.key_findings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Key Findings</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5">
              {report.key_findings.map((f, i) => (
                <li key={i} className="text-sm">{f}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {report.trends.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Trends</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5">
              {report.trends.map((t, i) => (
                <li key={i} className="text-sm">{t}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <p className="text-right text-xs text-muted-foreground">
        Generated at {report.generated_at}
      </p>
    </div>
  );
}
