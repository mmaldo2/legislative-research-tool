import Link from "next/link";
import {
  Search,
  Building2,
  Bot,
  FilePenLine,
  BarChart3,
  Shield,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      {/* Hero */}
      <div className="flex flex-col items-center text-center">
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10">
          <FilePenLine className="h-8 w-8 text-primary" />
        </div>
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          The Policy Drafting IDE
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
          Draft model legislation grounded in real legislative data, AI analysis,
          and ML-powered predictions across 50 states and Congress. Research and
          write in one integrated environment.
        </p>
        <div className="mt-8 flex gap-3">
          <Button asChild size="lg">
            <Link href="/composer">
              <FilePenLine className="mr-2 h-4 w-4" />
              Start Drafting
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/search">
              <Search className="mr-2 h-4 w-4" />
              Explore Research
            </Link>
          </Button>
        </div>
      </div>

      {/* How it works — Composer workflow */}
      <div className="mt-20">
        <h2 className="mb-8 text-center text-2xl font-semibold tracking-tight">
          How It Works
        </h2>
        <div className="grid gap-4 sm:grid-cols-4">
          {[
            { step: "1", title: "Select Precedents", desc: "Choose real bills as the foundation for your draft" },
            { step: "2", title: "Generate Outline", desc: "AI synthesizes a jurisdiction-aware bill structure" },
            { step: "3", title: "Draft & Analyze", desc: "Compose sections with AI, analyze for constitutional risks" },
            { step: "4", title: "Research & Refine", desc: "Ask the research assistant questions as you write" },
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

      {/* Feature cards — reordered: Composer first */}
      <div className="mt-16 grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
        <Card>
          <CardHeader>
            <FilePenLine className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>Policy Composer</CardTitle>
            <CardDescription>
              Build jurisdiction-aware drafting workspaces from precedent bills.
              AI-generated outlines, section-by-section composition, constitutional
              analysis, and an embedded research assistant.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Bot className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>Research Assistant</CardTitle>
            <CardDescription>
              10-tool agentic assistant that searches bills, analyzes constitutionality,
              detects cross-jurisdictional patterns, and suggests statutory language
              grounded in real precedents.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <BarChart3 className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>Bill Outcome Prediction</CardTitle>
            <CardDescription>
              ML stacking ensemble (0.997 AUROC) trained on 119K bills predicts committee
              passage probability. Top contributing factors shown per bill.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Search className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>Hybrid Search</CardTitle>
            <CardDescription>
              Keyword + semantic search powered by BM25 and legal embeddings
              with Reciprocal Rank Fusion across all 50 states and Congress.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Shield className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>Constitutional Analysis</CardTitle>
            <CardDescription>
              AI-powered analysis of First Amendment, Due Process, Equal Protection,
              Commerce Clause, and preemption concerns for any bill or draft.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Building2 className="mb-2 h-8 w-8 text-primary" />
            <CardTitle>50-State Coverage</CardTitle>
            <CardDescription>
              Federal and all 50 state legislatures with bill text, sponsors,
              actions, votes, and committee hearings.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    </div>
  );
}
