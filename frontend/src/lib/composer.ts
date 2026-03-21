export const COMPOSE_ACTION_OPTIONS = [
  { value: "draft_section", label: "Draft Section" },
  { value: "rewrite_selection", label: "Rewrite Selection" },
  { value: "tighten_definition", label: "Tighten Definitions" },
  { value: "harmonize_with_precedent", label: "Harmonize with Precedent" },
] as const;

export function formatComposeAction(action: string): string {
  return COMPOSE_ACTION_OPTIONS.find((o) => o.value === action)?.label ?? action;
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
