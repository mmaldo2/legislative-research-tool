export const COMPOSE_ACTION_OPTIONS = [
  { value: "draft_section", label: "Draft Section" },
  { value: "rewrite_selection", label: "Rewrite Selection" },
  { value: "tighten_definition", label: "Tighten Definitions" },
  { value: "harmonize_with_precedent", label: "Harmonize with Precedent" },
] as const;

export const ANALYZE_ACTION_OPTIONS = [
  { value: "analyze_constitutional", label: "Constitutional Analysis" },
  { value: "analyze_patterns", label: "Pattern Detection" },
] as const;

const ALL_ACTION_LABELS: Record<string, string> = {
  draft_section: "Draft Section",
  rewrite_selection: "Rewrite Selection",
  tighten_definition: "Tighten Definitions",
  harmonize_with_precedent: "Harmonize with Precedent",
  analyze_constitutional: "Constitutional Analysis",
  analyze_patterns: "Pattern Detection",
};

export function formatComposeAction(action: string): string {
  return ALL_ACTION_LABELS[action] ?? action;
}

export const COMPOSER_TEMPLATE_OPTIONS = [
  { value: "general-model-act", label: "General Model Act" },
  { value: "definitions-and-enforcement", label: "Definitions + Enforcement" },
  { value: "licensing-and-compliance", label: "Licensing + Compliance" },
] as const;

const COMPOSER_STATUS_LABELS: Record<string, string> = {
  setup: "Setup",
  outline_ready: "Outline Ready",
  outlined: "Outlined",
  edited: "Edited",
  drafting: "Drafting",
  archived: "Archived",
};

export function formatComposerTemplate(template: string): string {
  return COMPOSER_TEMPLATE_OPTIONS.find((option) => option.value === template)?.label ?? template;
}

export function formatComposerStatus(status: string): string {
  return COMPOSER_STATUS_LABELS[status] ?? status;
}
