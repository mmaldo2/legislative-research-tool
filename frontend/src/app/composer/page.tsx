"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  createPolicyWorkspace,
  deletePolicyWorkspace,
  listJurisdictions,
  listPolicyWorkspaces,
} from "@/lib/api";
import {
  COMPOSER_TEMPLATE_OPTIONS,
  formatComposerStatus,
  formatComposerTemplate,
} from "@/lib/composer";
import { formatJurisdiction } from "@/lib/format";
import type { JurisdictionResponse, PolicyWorkspaceResponse } from "@/types/api";
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
import { FilePenLine, Plus, Search, Trash2 } from "lucide-react";

export default function ComposerPage() {
  const [workspaces, setWorkspaces] = useState<PolicyWorkspaceResponse[]>([]);
  const [jurisdictions, setJurisdictions] = useState<JurisdictionResponse[]>([]);
  const [title, setTitle] = useState("");
  const [targetJurisdictionId, setTargetJurisdictionId] = useState("");
  const [draftingTemplate, setDraftingTemplate] = useState<string>(
    COMPOSER_TEMPLATE_OPTIONS[0].value,
  );
  const [goalPrompt, setGoalPrompt] = useState("");
  const [filterQuery, setFilterQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filteredWorkspaces = useMemo(() => {
    let result = workspaces;
    const q = filterQuery.trim().toLowerCase();
    if (q) {
      result = result.filter(
        (w) =>
          w.title.toLowerCase().includes(q) ||
          w.target_jurisdiction_id.toLowerCase().includes(q),
      );
    }
    if (filterStatus !== "all") {
      result = result.filter((w) => w.status === filterStatus);
    }
    return result;
  }, [workspaces, filterQuery, filterStatus]);

  async function load() {
    try {
      const [workspaceData, jurisdictionData] = await Promise.all([
        listPolicyWorkspaces(),
        listJurisdictions({ per_page: 100 }),
      ]);
      setWorkspaces(workspaceData.data);
      setJurisdictions(jurisdictionData.data);
      setTargetJurisdictionId((current) => {
        if (
          current &&
          jurisdictionData.data.some((jurisdiction) => jurisdiction.id === current)
        ) {
          return current;
        }
        return jurisdictionData.data[0]?.id ?? "";
      });
      setError(null);
    } catch (err) {
      console.error("Failed to load composer data:", err);
      setError("Failed to load composer.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleCreate() {
    if (!title.trim() || !targetJurisdictionId || !draftingTemplate) return;
    setCreating(true);
    try {
      await createPolicyWorkspace({
        title: title.trim(),
        target_jurisdiction_id: targetJurisdictionId,
        drafting_template: draftingTemplate,
        goal_prompt: goalPrompt.trim() || undefined,
      });
      setTitle("");
      setGoalPrompt("");
      await load();
    } catch (err) {
      console.error("Failed to create workspace:", err);
      setError("Failed to create workspace.");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deletePolicyWorkspace(id);
      await load();
    } catch (err) {
      console.error("Failed to delete workspace:", err);
      setError("Failed to delete workspace.");
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Composer</h1>
        <p className="mt-1 text-muted-foreground">
          Draft model legislation from precedent bills with a jurisdiction-aware workspace.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <Card className="mb-6">
        <CardHeader className="space-y-4">
          <CardTitle className="text-lg">Create Workspace</CardTitle>
          <div className="grid gap-3 md:grid-cols-2">
            <Input
              placeholder="Workspace title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <Select value={targetJurisdictionId} onValueChange={setTargetJurisdictionId}>
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
            <Select value={draftingTemplate} onValueChange={setDraftingTemplate}>
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
            <Input
              placeholder="Optional goal prompt"
              value={goalPrompt}
              onChange={(e) => setGoalPrompt(e.target.value)}
            />
          </div>
          <div>
            <Button
              onClick={handleCreate}
              disabled={creating || !title.trim() || !targetJurisdictionId}
            >
              <Plus className="mr-1.5 h-4 w-4" />
              {creating ? "Creating..." : "Create Workspace"}
            </Button>
          </div>
        </CardHeader>
      </Card>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-24 animate-pulse rounded-lg bg-muted/30" />
          ))}
        </div>
      ) : workspaces.length === 0 ? (
        <div className="rounded-lg border border-dashed px-6 py-10 text-center">
          <FilePenLine className="mx-auto mb-3 h-10 w-10 text-muted-foreground/60" />
          <p className="text-muted-foreground">
            No workspaces yet. Start with a jurisdiction-aware draft shell, then add precedent
            bills from the workspace detail page.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {workspaces.length > 1 && (
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Filter by title or jurisdiction..."
                  value={filterQuery}
                  onChange={(e) => setFilterQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="w-full sm:w-40">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="setup">Setup</SelectItem>
                  <SelectItem value="outline_ready">Outline Ready</SelectItem>
                  <SelectItem value="drafting">Drafting</SelectItem>
                  <SelectItem value="archived">Archived</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
          {filteredWorkspaces.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              No workspaces match your filter.
            </p>
          ) : null}
          {filteredWorkspaces.map((workspace) => (
            <Card key={workspace.id} className="transition-colors hover:bg-accent/50">
              <CardHeader className="flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <Link href={`/composer/${workspace.id}`} className="flex-1">
                  <CardTitle className="text-base">{workspace.title}</CardTitle>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <Badge variant="secondary">{formatComposerStatus(workspace.status)}</Badge>
                    <Badge variant="outline">
                      {formatJurisdiction(workspace.target_jurisdiction_id)}
                    </Badge>
                    <Badge variant="outline">
                      {formatComposerTemplate(workspace.drafting_template)}
                    </Badge>
                    <Badge variant="outline">{workspace.precedent_count} precedents</Badge>
                    <Badge variant="outline">{workspace.section_count} sections</Badge>
                  </div>
                </Link>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(workspace.id)}
                  aria-label={`Delete workspace ${workspace.title}`}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
