import Link from "next/link";
import {
  Search,
  Building2,
  Bot,
  FolderOpen,
  FileText,
  GitCompareArrows,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      <div className="flex flex-col items-center text-center">
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10">
          <FolderOpen className="h-8 w-8 text-primary" />
        </div>
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          The Policy Research Workspace
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
          Search across jurisdictions, build investigations around the bills that matter,
          compare legislative approaches, and generate grounded research outputs in one
          environment.
        </p>
        <div className="mt-8 flex gap-3">
          <Button asChild size="lg">
            <Link href="/collections">
              <FolderOpen className="mr-2 h-4 w-4" />
              Open Investigations
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/search">
              <Search className="mr-2 h-4 w-4" />
              Explore Search
            </Link>
          </Button>
        </div>
      </div>

      <div className="mt-20">
        <h2 className="mb-8 text-center text-2xl font-semibold tracking-tight">
          How It Works
        </h2>
        <div className="grid gap-4 sm:grid-cols-4">
          {[
            { step: "1", title: "Start an Investigation", desc: "Create a working set for a policy question or issue area" },
            { step: "2", title: "Search Across Jurisdictions", desc: "Find relevant bills, versions, and analogs across states and Congress" },
            { step: "3", title: "Compare and Analyze", desc: "Use the copilot and comparison tools to understand substantive differences" },
            { step: "4", title: "Generate a Research Output", desc: "Turn your working set into a memo, brief, or issue summary" },
          ].map((item) => (
            <div key={item.step} className="flex flex-col items-center text-center p-4">
              <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground font-bold text-sm">
                {item.step}
              </div>
              <h3 className="font-medium text-sm">{item.title}</h3>
              <p className="mt-1 text-xs text-muted-foreground">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-16 grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
        <Card>
          <CardHeader>
            <FolderOpen className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>Investigations</CardTitle>
            <CardDescription>
              Build working sets of relevant bills around a policy question, keep notes,
              and return to the same investigation as your research evolves.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <GitCompareArrows className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>Cross-Jurisdiction Comparison</CardTitle>
            <CardDescription>
              Compare similar bills, inspect version changes, and surface the differences
              that actually matter across states and sessions.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Bot className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>Grounded Research Assistant</CardTitle>
            <CardDescription>
              Use a tool-backed assistant to search bills, inspect details, find analogs,
              and answer follow-up questions over your active research context.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <FileText className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>Research Outputs</CardTitle>
            <CardDescription>
              Turn a search or investigation into a memo, comparative brief, or issue
              summary without leaving the workspace.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Search className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>Hybrid Search</CardTitle>
            <CardDescription>
              Search across all 50 states and Congress with keyword and semantic retrieval
              fused into one ranked result set.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Building2 className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>50-State Legislative Coverage</CardTitle>
            <CardDescription>
              Federal and state bills with text, sponsors, actions, versions, and related
              legislative context ready for deeper investigation.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    </div>
  );
}
