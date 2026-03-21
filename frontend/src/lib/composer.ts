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
