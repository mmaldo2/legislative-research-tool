import Link from "next/link";
import { Search, Building2, Users, Scale, FilePenLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      {/* Hero */}
      <div className="flex flex-col items-center text-center">
        <Scale className="mb-4 h-12 w-12 text-primary" />
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          Legislative Research Tool
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
          AI-native legislative research and drafting platform covering federal and 50-state
          legislation. Search, analyze, and turn precedent bills into jurisdiction-aware model
          legislation inside Composer.
        </p>
        <div className="mt-8 flex gap-3">
          <Button asChild size="lg">
            <Link href="/composer">
              <FilePenLine className="mr-2 h-4 w-4" />
              Open Composer
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/search">
              <Search className="mr-2 h-4 w-4" />
              Search Bills
            </Link>
          </Button>
        </div>
      </div>

      {/* Feature cards */}
      <div className="mt-20 grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <Search className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>Hybrid Search</CardTitle>
            <CardDescription>
              Keyword + semantic search powered by BM25 and Voyage-law-2
              embeddings with Reciprocal Rank Fusion.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <FilePenLine className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>Policy Composer</CardTitle>
            <CardDescription>
              Build jurisdiction-aware drafting workspaces, collect precedent bills, and prepare
              outline-driven model legislation in one place.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Building2 className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>50-State Coverage</CardTitle>
            <CardDescription>
              Federal and all 50 state legislatures. Filter by jurisdiction,
              session, status, and topic.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Users className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>AI Summaries</CardTitle>
            <CardDescription>
              Claude-powered structured summaries with key provisions, affected
              populations, and fiscal impact.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    </div>
  );
}
