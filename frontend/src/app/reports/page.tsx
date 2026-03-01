"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAnalysis } from "@/hooks/use-analysis";
import { generateReport } from "@/lib/api";
import { formatJurisdiction } from "@/lib/format";
import type { ReportOutput } from "@/types/api";

export default function ReportsPage() {
  const [query, setQuery] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [submitted, setSubmitted] = useState<{
    query: string;
    jurisdiction: string;
  } | null>(null);

  const fetcher = useCallback(
    (signal: AbortSignal) => {
      if (!submitted) return Promise.reject(new Error("No query"));
      return generateReport(
        submitted.query,
        submitted.jurisdiction || undefined,
        20,
        signal,
      );
    },
    [submitted],
  );

  const { result, loading, error, analyze } = useAnalysis<ReportOutput>(fetcher);

  // submitted changes -> fetcher recreated -> analyze recreated -> effect fires
  useEffect(() => {
    if (submitted) {
      analyze();
    }
  }, [submitted, analyze]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || query.trim().length < 3) return;
    setSubmitted({ query: query.trim(), jurisdiction: jurisdiction.trim() });
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Research Reports</h1>
        <p className="text-muted-foreground mt-1">
          Generate comprehensive policy research reports by searching across all
          jurisdictions.
        </p>
      </div>

      {/* Query Form */}
      <Card className="mb-6">
        <CardContent className="pt-6">
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
          {error && (
            <p className="mt-2 text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Report Output */}
      {result && <ReportView report={result} />}
    </div>
  );
}

function ReportView({ report }: { report: ReportOutput }) {
  return (
    <div className="space-y-4">
      {/* Title & Meta */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{report.title}</CardTitle>
          <div className="flex flex-wrap gap-2 mt-2">
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

      {/* Jurisdictions */}
      <div className="flex flex-wrap gap-1">
        {report.jurisdictions_covered.map((j) => (
          <Badge key={j} variant="secondary" className="text-xs">
            {formatJurisdiction(j)}
          </Badge>
        ))}
      </div>

      {/* Sections */}
      {report.sections.map((section, i) => (
        <Card key={i}>
          <CardHeader>
            <CardTitle className="text-lg">{section.heading}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="prose prose-sm max-w-none dark:prose-invert whitespace-pre-line">
              {section.content}
            </div>
          </CardContent>
        </Card>
      ))}

      {/* Key Findings */}
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

      {/* Trends */}
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

      {/* Footer */}
      <p className="text-xs text-muted-foreground text-right">
        Generated at {report.generated_at}
      </p>
    </div>
  );
}
