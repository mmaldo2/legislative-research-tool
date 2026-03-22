"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ApiError,
  RateLimitError,
  acceptPolicyGeneration,
  addPolicyWorkspacePrecedent,
  clientHeaders,
  composePolicySection,
  generatePolicyWorkspaceOutline,
  getPolicyWorkspace,
  getPolicyWorkspaceExportUrl,
  getPolicyWorkspaceHistory,
  listJurisdictions,
  removePolicyWorkspacePrecedent,
  searchBills,
  updatePolicyWorkspace,
  updatePolicyWorkspaceSection,
} from "@/lib/api";
import {
  COMPOSE_ACTION_OPTIONS,
  COMPOSER_TEMPLATE_OPTIONS,
  formatComposeAction,
  formatComposerStatus,
  formatComposerTemplate,
} from "@/lib/composer";
import { formatJurisdiction, formatStatus, statusVariant } from "@/lib/format";
import type {
  JurisdictionResponse,
  PolicyGenerationResponse,
  PolicyRevisionResponse,
  PolicyWorkspaceDetailResponse,
  SearchResult,
} from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Download,
  Plus,
  Save,
  Search,
  Trash2,
  WandSparkles,
  X,
} from "lucide-react";
import { ApiErrorBanner } from "@/components/api-error";

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError || error instanceof RateLimitError) {
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export default function ComposerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  if (!id) {
    notFound();
  }

  const [workspace, setWorkspace] = useState<PolicyWorkspaceDetailResponse | null>(null);
  const [jurisdictions, setJurisdictions] = useState<JurisdictionResponse[]>([]);
  const [workspaceTitle, setWorkspaceTitle] = useState("");
  const [targetJurisdictionId, setTargetJurisdictionId] = useState("");
  const [draftingTemplate, setDraftingTemplate] = useState<string>(COMPOSER_TEMPLATE_OPTIONS[0].value);
  const [goalPrompt, setGoalPrompt] = useState("");
  const [billId, setBillId] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [sectionDrafts, setSectionDrafts] = useState<Record<string, { heading: string; purpose: string }>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchExecuted, setSearchExecuted] = useState(false);
  const [generatingOutline, setGeneratingOutline] = useState(false);
  const [savingSectionId, setSavingSectionId] = useState<string | null>(null);
  const [composingId, setComposingId] = useState<string | null>(null);
  const [pendingGenerations, setPendingGenerations] = useState<Record<string, PolicyGenerationResponse>>({});
  const [acceptingId, setAcceptingId] = useState<string | null>(null);
  const [sectionHistory, setSectionHistory] = useState<Record<string, PolicyRevisionResponse[]>>({});
  const [expandedHistory, setExpandedHistory] = useState<Set<string>>(new Set());
  const [researchQuery, setResearchQuery] = useState("");
  const [researchResults, setResearchResults] = useState<SearchResult[]>([]);
  const [researching, setResearching] = useState(false);
  const [researchOpen, setResearchOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  const selectedBillIds = useMemo(
    () => new Set(workspace?.precedents.map((precedent) => precedent.bill_id) ?? []),
    [workspace],
  );

  function syncSectionDrafts(data: PolicyWorkspaceDetailResponse) {
    setSectionDrafts(
      Object.fromEntries(
        data.sections.map((section) => [
          section.id,
          {
            heading: section.heading,
            purpose: section.purpose ?? "",
          },
        ]),
      ),
    );
  }

  const load = useCallback(async () => {
    try {
      const [workspaceData, jurisdictionData] = await Promise.all([
        getPolicyWorkspace(id),
        listJurisdictions({ per_page: 100 }),
      ]);
      setWorkspace(workspaceData);
      setJurisdictions(jurisdictionData.data);
      setWorkspaceTitle(workspaceData.title);
      setTargetJurisdictionId(workspaceData.target_jurisdiction_id);
      setDraftingTemplate(workspaceData.drafting_template);
      setGoalPrompt(workspaceData.goal_prompt ?? "");
      syncSectionDrafts(workspaceData);
      setError(null);
    } catch (err) {
      console.error("Failed to load workspace:", err);
      setError(getErrorMessage(err, "Failed to load workspace."));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleAddPrecedent() {
    if (!billId.trim()) return;
    setSaving(true);
    try {
      await addPolicyWorkspacePrecedent(id, billId.trim());
      setBillId("");
      await load();
      setError(null);
    } catch (err) {
      console.error("Failed to add precedent:", err);
      setError(getErrorMessage(err, "Failed to add precedent bill."));
    } finally {
      setSaving(false);
    }
  }

  async function handleSearch() {
    const query = searchQuery.trim();
    if (!query) {
      setSearchResults([]);
      setSearchExecuted(false);
      setSearchError(null);
      return;
    }

    setSearching(true);
    setSearchExecuted(true);
    try {
      const data = await searchBills({
        q: query,
        page: 1,
        per_page: 6,
      });
      setSearchResults(data.data);
      setSearchError(null);
    } catch (err) {
      console.error("Failed to search bills:", err);
      setSearchError(getErrorMessage(err, "Failed to search bills."));
    } finally {
      setSearching(false);
    }
  }

  async function handleAddSearchResult(billIdToAdd: string) {
    setSaving(true);
    try {
      await addPolicyWorkspacePrecedent(id, billIdToAdd);
      await load();
      setError(null);
    } catch (err) {
      console.error("Failed to add precedent:", err);
      setError(getErrorMessage(err, "Failed to add precedent bill."));
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveWorkspace() {
    if (!workspace || !workspaceTitle.trim() || !targetJurisdictionId || !draftingTemplate) {
      return;
    }

    setSaving(true);
    try {
      await updatePolicyWorkspace(workspace.id, {
        title: workspaceTitle.trim(),
        target_jurisdiction_id: targetJurisdictionId,
        drafting_template: draftingTemplate,
        goal_prompt: goalPrompt.trim() || null,
      });
      await load();
      setError(null);
    } catch (err) {
      console.error("Failed to update workspace:", err);
      setError(getErrorMessage(err, "Failed to update workspace settings."));
    } finally {
      setSaving(false);
    }
  }

  async function handleRemovePrecedent(precedentBillId: string) {
    try {
      await removePolicyWorkspacePrecedent(id, precedentBillId);
      await load();
      setError(null);
    } catch (err) {
      console.error("Failed to remove precedent:", err);
      setError(getErrorMessage(err, "Failed to remove precedent bill."));
    }
  }

  async function handleGenerateOutline() {
    if (!workspace) return;

    setGeneratingOutline(true);
    try {
      const data = await generatePolicyWorkspaceOutline(workspace.id);
      setWorkspace(data);
      syncSectionDrafts(data);
      setError(null);
    } catch (err) {
      console.error("Failed to generate outline:", err);
      setError(getErrorMessage(err, "Failed to generate outline."));
    } finally {
      setGeneratingOutline(false);
    }
  }

  async function handleSaveSection(sectionId: string) {
    const section = workspace?.sections.find((candidate) => candidate.id === sectionId);
    const draft = sectionDrafts[sectionId];
    if (!section || !draft || !draft.heading.trim()) return;

    setSavingSectionId(sectionId);
    try {
      await updatePolicyWorkspaceSection(id, sectionId, {
        heading: draft.heading.trim(),
        purpose: draft.purpose.trim() || null,
      });
      await load();
      setError(null);
    } catch (err) {
      console.error("Failed to update section:", err);
      setError(getErrorMessage(err, "Failed to update outline section."));
    } finally {
      setSavingSectionId(null);
    }
  }

  async function handleExport() {
    if (!workspace) return;
    try {
      const res = await fetch(getPolicyWorkspaceExportUrl(workspace.id), {
        headers: clientHeaders(),
      });
      if (!res.ok) {
        setError("Failed to export workspace.");
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${workspace.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export:", err);
      setError(getErrorMessage(err, "Failed to export workspace."));
    }
  }

  async function handleResearch() {
    const query = researchQuery.trim();
    if (!query || !workspace) return;
    setResearching(true);
    try {
      const data = await searchBills({
        q: query,
        jurisdiction: workspace.target_jurisdiction_id,
        per_page: 8,
      });
      setResearchResults(data.data);
      setError(null);
    } catch (err) {
      console.error("Failed to search:", err);
      setError(getErrorMessage(err, "Failed to search legislation."));
    } finally {
      setResearching(false);
    }
  }

  async function handleCompose(sectionId: string, actionType: string) {
    setComposingId(sectionId);
    setPendingGenerations((prev) => {
      const next = { ...prev };
      delete next[sectionId];
      return next;
    });
    try {
      const gen = await composePolicySection(id, sectionId, {
        action_type: actionType,
      });
      setPendingGenerations((prev) => ({ ...prev, [sectionId]: gen }));
      setError(null);
    } catch (err) {
      console.error("Failed to compose section:", err);
      setError(getErrorMessage(err, "Failed to compose section."));
    } finally {
      setComposingId(null);
    }
  }

  async function handleAccept(sectionId: string, generationId: string) {
    if (!workspace) return;
    setAcceptingId(generationId);
    try {
      await acceptPolicyGeneration(workspace.id, generationId);
      setPendingGenerations((prev) => {
        const next = { ...prev };
        delete next[sectionId];
        return next;
      });
      await load();
      setError(null);
    } catch (err) {
      console.error("Failed to accept generation:", err);
      setError(getErrorMessage(err, "Failed to accept generation."));
    } finally {
      setAcceptingId(null);
    }
  }

  function handleRejectGeneration(sectionId: string) {
    setPendingGenerations((prev) => {
      const next = { ...prev };
      delete next[sectionId];
      return next;
    });
  }

  async function toggleHistory(sectionId: string) {
    const next = new Set(expandedHistory);
    if (next.has(sectionId)) {
      next.delete(sectionId);
      setExpandedHistory(next);
      return;
    }
    try {
      const data = await getPolicyWorkspaceHistory(id, sectionId);
      setSectionHistory((prev) => ({ ...prev, [sectionId]: data.revisions }));
      next.add(sectionId);
      setExpandedHistory(next);
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div className="h-8 w-64 animate-pulse rounded bg-muted/30 mb-6" />
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-24 animate-pulse rounded-lg bg-muted/30" />
          ))}
        </div>
      </div>
    );
  }

  if (!workspace) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <Link
          href="/composer"
          className="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to composer
        </Link>
        {error ? (
          <ApiErrorBanner message={error} className="mt-4" />
        ) : (
          <p className="text-muted-foreground">Workspace not found.</p>
        )}
      </div>
    );
  }

  const shouldShowSearchResults =
    searchResults.length > 0 || Boolean(searchError) || searchExecuted;
  const hasOutline = workspace.sections.length > 0;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <Link
        href="/composer"
        className="inline-flex items-center gap-1 text-sm text-primary hover:underline mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to composer
      </Link>

      <div className="mb-6">
        <h1 className="text-2xl font-bold">{workspace.title}</h1>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge variant="secondary">{formatComposerStatus(workspace.status)}</Badge>
          <Badge variant="outline">
            {formatJurisdiction(workspace.target_jurisdiction_id)}
          </Badge>
          <Badge variant="outline">{formatComposerTemplate(workspace.drafting_template)}</Badge>
        </div>
        {workspace.goal_prompt && (
          <p className="mt-3 text-sm text-muted-foreground">{workspace.goal_prompt}</p>
        )}
        {workspace.sections.length > 0 && (
          <div className="mt-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleExport()}
            >
              <Download className="mr-1.5 h-4 w-4" />
              Export Markdown
            </Button>
          </div>
        )}
      </div>

      {error && <ApiErrorBanner message={error} className="mb-4" />}

      <Card className="mb-6">
        <CardHeader className="space-y-4">
          <CardTitle className="text-lg">Workspace Settings</CardTitle>
          <div className="grid gap-3 md:grid-cols-2">
            <Input value={workspaceTitle} onChange={(e) => setWorkspaceTitle(e.target.value)} />
            <Select
              value={targetJurisdictionId}
              onValueChange={setTargetJurisdictionId}
              disabled={hasOutline}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Target jurisdiction" />
              </SelectTrigger>
              <SelectContent>
                {jurisdictions.map((jurisdiction) => (
                  <SelectItem key={jurisdiction.id} value={jurisdiction.id}>
                    {jurisdiction.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={draftingTemplate}
              onValueChange={setDraftingTemplate}
              disabled={hasOutline}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Drafting template" />
              </SelectTrigger>
              <SelectContent>
                {COMPOSER_TEMPLATE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <textarea
              value={goalPrompt}
              onChange={(e) => setGoalPrompt(e.target.value)}
              placeholder="Optional policy goal or drafting brief"
              className="min-h-24 rounded-md border bg-background px-3 py-2 text-sm md:col-span-2"
            />
          </div>
          {hasOutline && (
            <p className="text-sm text-muted-foreground">
              Target jurisdiction and drafting template are locked once an outline is generated.
            </p>
          )}
          <div>
            <Button
              onClick={handleSaveWorkspace}
              disabled={saving || !workspaceTitle.trim() || !targetJurisdictionId}
            >
              <Save className="mr-1.5 h-4 w-4" />
              Save Settings
            </Button>
          </div>
        </CardHeader>
      </Card>

      <Card className="mb-6">
        <CardHeader className="space-y-4">
          <CardTitle className="text-lg">Precedent Bills</CardTitle>
          <div className="flex gap-2">
            <Input
              placeholder="Search precedents by topic, identifier, or clause"
              value={searchQuery}
              onChange={(e) => {
                const value = e.target.value;
                setSearchQuery(value);
                if (!value.trim()) {
                  setSearchResults([]);
                  setSearchExecuted(false);
                  setSearchError(null);
                }
              }}
              onKeyDown={(e) => e.key === "Enter" && void handleSearch()}
              disabled={hasOutline}
            />
            <Button
              onClick={handleSearch}
              disabled={hasOutline || searching || !searchQuery.trim()}
            >
              <Search className="mr-1.5 h-4 w-4" />
              {searching ? "Searching..." : "Search"}
            </Button>
          </div>
          {hasOutline && (
            <p className="text-sm text-muted-foreground">
              Precedents are locked after outline generation to keep the draft grounded in a stable
              source set.
            </p>
          )}
          {searchError && (
            <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {searchError}
            </div>
          )}
          {shouldShowSearchResults && (
            <div className="space-y-3">
              {searchResults.map((result) => (
                <Card key={result.bill_id}>
                  <CardHeader className="flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="flex-1">
                      <Link
                        href={`/bills/${encodeURIComponent(result.bill_id)}`}
                        className="font-medium hover:underline"
                      >
                        {result.identifier}
                      </Link>
                      <p className="mt-1 text-sm text-muted-foreground">{result.title}</p>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs">
                        <Badge variant="outline">
                          {formatJurisdiction(result.jurisdiction_id)}
                        </Badge>
                        {result.status && (
                          <Badge variant={statusVariant(result.status)}>
                            {formatStatus(result.status)}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant={selectedBillIds.has(result.bill_id) ? "outline" : "default"}
                      disabled={hasOutline || saving || selectedBillIds.has(result.bill_id)}
                      onClick={() => void handleAddSearchResult(result.bill_id)}
                    >
                      <Plus className="mr-1.5 h-4 w-4" />
                      {selectedBillIds.has(result.bill_id) ? "Selected" : "Add"}
                    </Button>
                  </CardHeader>
                </Card>
              ))}
              {!searchError && searchResults.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No precedent candidates matched this search.
                </p>
              )}
            </div>
          )}
          <div className="flex gap-2">
            <Input
              placeholder="Quick add by bill ID"
              value={billId}
              onChange={(e) => setBillId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddPrecedent()}
              disabled={hasOutline}
            />
            <Button onClick={handleAddPrecedent} disabled={hasOutline || saving || !billId.trim()}>
              <Plus className="mr-1.5 h-4 w-4" />
              Add
            </Button>
          </div>
          {workspace.precedents.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No precedents selected yet. Search for bills above or add one directly by bill ID.
            </p>
          ) : (
            <div className="space-y-3">
              {workspace.precedents.map((precedent) => (
                <Card key={precedent.id}>
                  <CardHeader className="flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex-1">
                      <Link
                        href={`/bills/${encodeURIComponent(precedent.bill_id)}`}
                        className="font-medium hover:underline"
                      >
                        {precedent.identifier}
                      </Link>
                      <p className="mt-1 text-sm text-muted-foreground">{precedent.title}</p>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs">
                        <Badge variant="outline">
                          {formatJurisdiction(precedent.jurisdiction_id)}
                        </Badge>
                        {precedent.status && (
                          <Badge variant={statusVariant(precedent.status)}>
                            {formatStatus(precedent.status)}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemovePrecedent(precedent.bill_id)}
                      aria-label={`Remove ${precedent.identifier}`}
                      disabled={hasOutline}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </CardHeader>
                </Card>
              ))}
            </div>
          )}
        </CardHeader>
      </Card>

      {hasOutline && (
        <Card className="mb-6">
          <CardHeader className="space-y-3">
            <button
              type="button"
              className="flex items-center gap-2 text-left"
              onClick={() => setResearchOpen(!researchOpen)}
            >
              {researchOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              <CardTitle className="text-lg">Research</CardTitle>
              <span className="text-sm text-muted-foreground">
                Search legislation in {formatJurisdiction(workspace.target_jurisdiction_id)}
              </span>
            </button>
            {researchOpen && (
              <>
                <div className="flex gap-2">
                  <Input
                    placeholder="Search for definitions, clauses, enforcement language..."
                    value={researchQuery}
                    onChange={(e) => setResearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && void handleResearch()}
                  />
                  <Button
                    onClick={handleResearch}
                    disabled={researching || !researchQuery.trim()}
                  >
                    <Search className="mr-1.5 h-4 w-4" />
                    {researching ? "Searching..." : "Search"}
                  </Button>
                </div>
                {researchResults.length > 0 && (
                  <div className="space-y-2">
                    {researchResults.map((result) => (
                      <div key={result.bill_id} className="rounded-md border p-3 text-sm">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <Link
                              href={`/bills/${encodeURIComponent(result.bill_id)}`}
                              className="font-medium hover:underline"
                            >
                              {result.identifier}
                            </Link>
                            <span className="ml-2 text-muted-foreground">
                              {formatJurisdiction(result.jurisdiction_id)}
                            </span>
                          </div>
                          {result.score !== undefined && (
                            <Badge variant="outline" className="text-xs">
                              {(result.score * 100).toFixed(0)}% match
                            </Badge>
                          )}
                        </div>
                        <p className="mt-1 text-muted-foreground">{result.title}</p>
                        {result.snippet && (
                          <p className="mt-2 rounded bg-muted/30 px-2 py-1 text-xs text-muted-foreground">
                            {result.snippet}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </CardHeader>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Outline</CardTitle>
          {workspace.sections.length === 0 ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Generate a proposed bill outline once your target jurisdiction, drafting template,
                and precedent set are ready.
              </p>
              <div>
                <Button
                  onClick={handleGenerateOutline}
                  disabled={generatingOutline || workspace.precedents.length === 0}
                >
                  <WandSparkles className="mr-1.5 h-4 w-4" />
                  {generatingOutline ? "Generating..." : "Generate Outline"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                {workspace.outline_generated_at && (
                  <Badge variant="outline">
                    Generated {new Date(workspace.outline_generated_at).toLocaleString()}
                  </Badge>
                )}
                {workspace.outline_confidence !== null && (
                  <Badge variant="outline">
                    {(workspace.outline_confidence * 100).toFixed(0)}% confidence
                  </Badge>
                )}
              </div>
              {workspace.outline_drafting_notes.length > 0 && (
                <div className="rounded-md border border-dashed p-3">
                  <p className="text-sm font-medium">Drafting Notes</p>
                  <div className="mt-2 space-y-2">
                    {workspace.outline_drafting_notes.map((note) => (
                      <p key={note} className="text-sm text-muted-foreground">
                        {note}
                      </p>
                    ))}
                  </div>
                </div>
              )}
              {workspace.sections.map((section) => (
                <div key={section.id} className="rounded-md border p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline">Section {section.position + 1}</Badge>
                      <Badge variant="secondary">{formatComposerStatus(section.status)}</Badge>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => void handleSaveSection(section.id)}
                      disabled={
                        savingSectionId === section.id ||
                        !sectionDrafts[section.id] ||
                        (sectionDrafts[section.id].heading.trim() === section.heading &&
                          sectionDrafts[section.id].purpose === (section.purpose ?? ""))
                      }
                    >
                      <Save className="mr-1.5 h-4 w-4" />
                      {savingSectionId === section.id ? "Saving..." : "Save Section"}
                    </Button>
                  </div>
                  <div className="mt-3 space-y-3">
                    <Input
                      value={sectionDrafts[section.id]?.heading ?? section.heading}
                      onChange={(e) =>
                        setSectionDrafts((current) => ({
                          ...current,
                          [section.id]: {
                            heading: e.target.value,
                            purpose: current[section.id]?.purpose ?? section.purpose ?? "",
                          },
                        }))
                      }
                    />
                    <textarea
                      value={sectionDrafts[section.id]?.purpose ?? section.purpose ?? ""}
                      onChange={(e) =>
                        setSectionDrafts((current) => ({
                          ...current,
                          [section.id]: {
                            heading: current[section.id]?.heading ?? section.heading,
                            purpose: e.target.value,
                          },
                        }))
                      }
                      placeholder="Section purpose"
                      className="min-h-16 w-full rounded-md border bg-background px-3 py-2 text-sm"
                    />
                  </div>

                  {/* Drafted content */}
                  {section.content_markdown && (
                    <div className="mt-4 rounded-md border bg-muted/30 p-3">
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Current Draft
                      </p>
                      <div className="whitespace-pre-wrap text-sm">
                        {section.content_markdown}
                      </div>
                    </div>
                  )}

                  {/* Compose actions */}
                  <div className="mt-4 flex flex-wrap gap-2">
                    {COMPOSE_ACTION_OPTIONS.map((action) => {
                      const needsContent =
                        action.value !== "draft_section" && !section.content_markdown;
                      return (
                        <Button
                          key={action.value}
                          size="sm"
                          variant="outline"
                          disabled={composingId === section.id || needsContent}
                          onClick={() => void handleCompose(section.id, action.value)}
                        >
                          <WandSparkles className="mr-1.5 h-3 w-3" />
                          {composingId === section.id ? "Composing..." : action.label}
                        </Button>
                      );
                    })}
                  </div>

                  {/* Pending generation */}
                  {pendingGenerations[section.id] && (() => {
                    const pg = pendingGenerations[section.id];
                    return (
                    <div className="mt-4 rounded-md border border-primary/30 bg-primary/5 p-4">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="outline">
                            {formatComposeAction(pg.action_type)}
                          </Badge>
                          <Badge variant="secondary">Pending Review</Badge>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            onClick={() => void handleAccept(section.id, pg.id)}
                            disabled={acceptingId === pg.id}
                          >
                            <Check className="mr-1.5 h-3 w-3" />
                            {acceptingId === pg.id ? "Accepting..." : "Accept"}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleRejectGeneration(section.id)}
                          >
                            <X className="mr-1.5 h-3 w-3" />
                            Reject
                          </Button>
                        </div>
                      </div>
                      {pg.rationale && (
                        <p className="mt-2 text-sm text-muted-foreground">
                          {pg.rationale}
                        </p>
                      )}
                      <div className="mt-3 whitespace-pre-wrap rounded-md border bg-background p-3 text-sm">
                        {pg.output_markdown}
                      </div>
                      {pg.provenance.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {pg.provenance.map((source) => (
                            <div
                              key={source.bill_id}
                              className="rounded-md border px-2 py-1 text-xs"
                            >
                              {source.identifier}
                              {source.note && (
                                <span className="ml-1 text-muted-foreground">
                                  — {source.note}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    );
                  })()}

                  {/* Provenance */}
                  {section.provenance.length > 0 && (
                    <div className="mt-4 space-y-2">
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Provenance
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {section.provenance.map((source) => (
                          <div
                            key={`${section.id}-${source.bill_id}`}
                            className="rounded-md border px-3 py-2 text-xs"
                          >
                            <Link
                              href={`/bills/${encodeURIComponent(source.bill_id)}`}
                              className="font-medium hover:underline"
                            >
                              {source.identifier}
                            </Link>
                            <p className="mt-1 text-muted-foreground">
                              {formatJurisdiction(source.jurisdiction_id)}
                            </p>
                            {source.note && (
                              <p className="mt-1 text-muted-foreground">{source.note}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* History toggle */}
                  <div className="mt-4">
                    <button
                      type="button"
                      className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                      onClick={() => void toggleHistory(section.id)}
                    >
                      {expandedHistory.has(section.id) ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : (
                        <ChevronRight className="h-3 w-3" />
                      )}
                      <Clock className="h-3 w-3" />
                      Revision History
                    </button>
                    {expandedHistory.has(section.id) && (
                      <div className="mt-2 space-y-2">
                        {(sectionHistory[section.id] ?? []).length === 0 ? (
                          <p className="text-xs text-muted-foreground">No revisions yet.</p>
                        ) : (
                          (sectionHistory[section.id] ?? []).map((rev) => (
                            <div key={rev.id} className="rounded-md border p-2 text-xs">
                              <div className="flex items-center gap-2">
                                <Badge variant="outline">{rev.change_source}</Badge>
                                {rev.created_at && (
                                  <span className="text-muted-foreground">
                                    {new Date(rev.created_at).toLocaleString()}
                                  </span>
                                )}
                              </div>
                              <p className="mt-1 line-clamp-3 text-muted-foreground">
                                {rev.content_markdown.slice(0, 200)}
                                {rev.content_markdown.length > 200 ? "..." : ""}
                              </p>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardHeader>
      </Card>
    </div>
  );
}
