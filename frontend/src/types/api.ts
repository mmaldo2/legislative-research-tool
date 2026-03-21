/** TypeScript interfaces matching the FastAPI Pydantic schemas. */

// --- Common ---

export interface MetaResponse {
  sources: string[];
  last_updated: string | null;
  ai_enriched: boolean;
  ai_model: string | null;
  ai_prompt_version: string | null;
  total_count: number | null;
  page: number | null;
  per_page: number | null;
}

// --- Bills ---

export interface BillSummary {
  id: string;
  jurisdiction_id: string;
  session_id: string;
  identifier: string;
  title: string;
  status: string | null;
  status_date: string | null;
  classification: string[] | null;
  subject: string[] | null;
}

export interface BillTextResponse {
  id: string;
  version_name: string;
  version_date: string | null;
  content_text: string | null;
  source_url: string | null;
  word_count: number | null;
}

export interface BillActionResponse {
  action_date: string;
  description: string;
  classification: string[] | null;
  chamber: string | null;
}

export interface SponsorResponse {
  person_id: string;
  name: string;
  party: string | null;
  classification: string;
}

export interface BillDetailResponse {
  id: string;
  jurisdiction_id: string;
  session_id: string;
  identifier: string;
  title: string;
  status: string | null;
  status_date: string | null;
  classification: string[] | null;
  subject: string[] | null;
  source_urls: string[] | null;
  created_at: string | null;
  updated_at: string | null;
  ai_summary: BillSummaryOutput | null;
  texts: BillTextResponse[];
  actions: BillActionResponse[];
  sponsors: SponsorResponse[];
}

export interface BillListResponse {
  data: BillSummary[];
  meta: MetaResponse;
}

// --- Search ---

export interface SearchResult {
  bill_id: string;
  identifier: string;
  title: string;
  jurisdiction_id: string;
  status: string | null;
  score: number;
  snippet: string | null;
}

export interface SearchResponse {
  data: SearchResult[];
  meta: MetaResponse;
}

// --- People ---

export interface PersonResponse {
  id: string;
  name: string;
  party: string | null;
  current_jurisdiction_id: string | null;
  current_chamber: string | null;
  current_district: string | null;
  image_url: string | null;
}

export interface PersonListResponse {
  data: PersonResponse[];
  meta: MetaResponse;
}

export interface PersonVoteResponse {
  vote_event_id: string;
  bill_id: string;
  bill_identifier: string;
  bill_title: string;
  vote_date: string | null;
  chamber: string | null;
  motion_text: string | null;
  result: string | null;
  option: string;
}

export interface PersonVoteListResponse {
  data: PersonVoteResponse[];
  meta: MetaResponse;
}

export interface PersonStatsResponse {
  bills_sponsored: number;
  bills_cosponsored: number;
  votes_cast: number;
  vote_participation_rate: number | null;
}

// --- Jurisdictions ---

export interface JurisdictionResponse {
  id: string;
  name: string;
  classification: string;
  abbreviation: string | null;
  fips_code: string | null;
}

export interface JurisdictionListResponse {
  data: JurisdictionResponse[];
  meta: MetaResponse;
}

export interface SessionBillCount {
  session_id: string;
  session_name: string;
  bill_count: number;
}

export interface SubjectCount {
  subject: string;
  count: number;
}

export interface JurisdictionStatsResponse {
  total_bills: number;
  total_legislators: number;
  bills_by_status: Record<string, number>;
  bills_by_session: SessionBillCount[];
  top_subjects: SubjectCount[];
}

// --- Sessions ---

export interface SessionResponse {
  id: string;
  jurisdiction_id: string;
  name: string;
  identifier: string;
  classification: string | null;
  start_date: string | null;
  end_date: string | null;
}

export interface SessionListResponse {
  data: SessionResponse[];
  meta: MetaResponse;
}

// --- Votes ---

export interface VoteRecordResponse {
  person_id: string;
  person_name: string | null;
  option: string;
}

export interface VoteEventResponse {
  id: string;
  bill_id: string;
  vote_date: string | null;
  chamber: string | null;
  motion_text: string | null;
  result: string | null;
  yes_count: number | null;
  no_count: number | null;
  other_count: number | null;
  records: VoteRecordResponse[];
}

export interface VoteEventListResponse {
  data: VoteEventResponse[];
  meta: MetaResponse;
}

// --- Analysis ---

export interface BillSummaryOutput {
  plain_english_summary: string;
  key_provisions: string[];
  affected_populations: string[];
  changes_to_existing_law: string[];
  fiscal_implications: string | null;
  effective_date: string | null;
  confidence: number;
}

// --- Version Diff ---

export type ChangeType = "added" | "removed" | "modified";
export type Significance = "major" | "moderate" | "minor";
export type Severity = "high" | "moderate" | "low";
export type RiskLevel = "high" | "moderate" | "low" | "minimal" | "unknown";
export type PatternType = "identical" | "adapted" | "inspired" | "coincidental" | "unknown";

export interface VersionDiffChange {
  section: string;
  change_type: ChangeType;
  significance: Significance;
  before: string | null;
  after: string | null;
  description: string;
}

export interface VersionDiffOutput {
  version_a_name: string;
  version_b_name: string;
  changes: VersionDiffChange[];
  summary_of_changes: string;
  direction_of_change: string;
  amendments_incorporated: string[];
  confidence: number;
}

// --- Constitutional Analysis ---

export interface ConstitutionalConcern {
  provision: string;
  severity: Severity;
  bill_section: string;
  description: string;
  relevant_precedents: string[];
}

export interface ConstitutionalAnalysisOutput {
  concerns: ConstitutionalConcern[];
  preemption_issues: string[];
  has_severability_clause: boolean;
  overall_risk_level: RiskLevel;
  summary: string;
  confidence: number;
}

// --- Pattern Detection ---

export interface PatternBillInfo {
  bill_id: string;
  identifier: string;
  jurisdiction_id: string;
  title: string;
  variations: string[];
}

export interface PatternDetectionOutput {
  pattern_type: PatternType;
  common_framework: string;
  source_organization: string | null;
  bills_analyzed: PatternBillInfo[];
  shared_provisions: string[];
  key_variations: string[];
  model_legislation_confidence: number;
  summary: string;
  confidence: number;
}

// --- Diffusion ---

export interface DiffusionEvent {
  bill_id: string;
  identifier: string;
  jurisdiction_id: string;
  title: string;
  status: string | null;
  status_date: string | null;
  similarity_score: number;
}

export interface DiffusionOutput {
  source_bill_id: string;
  source_identifier: string;
  source_jurisdiction: string;
  source_date: string | null;
  timeline: DiffusionEvent[];
  total_jurisdictions: number;
  earliest_date: string | null;
  latest_date: string | null;
  summary: string;
  confidence: number;
}

// --- Prediction ---

export type PredictionDirection = "positive" | "negative" | "neutral";
export type PredictionWeight = "high" | "moderate" | "low";
export type PredictedOutcome = "pass" | "fail" | "stall" | "uncertain";

export interface PredictionFactor {
  factor: string;
  direction: PredictionDirection;
  weight: PredictionWeight;
  explanation: string;
}

export interface PredictionOutput {
  predicted_outcome: PredictedOutcome;
  confidence: number;
  passage_probability: number;
  key_factors: PredictionFactor[];
  historical_comparison: string;
  summary: string;
}

// --- ML Prediction (GET /bills/{id}/prediction) ---

export interface MLPredictionFactor {
  feature: string;
  value: number;
  impact: "positive" | "negative";
}

export interface MLPredictionResponse {
  bill_id: string;
  committee_passage_probability: number;
  model_version: string;
  key_factors: MLPredictionFactor[];
  base_rate: number;
  meta: MetaResponse;
}

// --- Reports ---

export interface ReportSection {
  heading: string;
  content: string;
}

export interface ReportOutput {
  title: string;
  executive_summary: string;
  sections: ReportSection[];
  bills_analyzed: number;
  jurisdictions_covered: string[];
  key_findings: string[];
  trends: string[];
  generated_at: string;
  confidence: number;
}

// --- Status ---

export interface HealthResponse {
  status: string;
  version: string;
  database: string;
}

export interface IngestionRunResponse {
  id: number;
  source: string;
  run_type: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  records_created: number;
  records_updated: number;
}

export interface StatusResponse {
  total_bills: number;
  total_jurisdictions: number;
  recent_runs: IngestionRunResponse[];
}

// --- Compare ---

export interface SimilarBillResult {
  bill_id: string;
  identifier: string;
  title: string;
  jurisdiction_id: string;
  status: string | null;
  similarity_score: number;
}

export interface SimilarBillsResponse {
  data: SimilarBillResult[];
  meta: MetaResponse;
}

export interface BillComparisonOutput {
  shared_provisions: string[];
  unique_to_a: string[];
  unique_to_b: string[];
  key_differences: string[];
  overall_assessment: string;
  similarity_score: number;
  is_model_legislation: boolean;
  confidence: number;
}

// --- Collections ---

export interface CollectionResponse {
  id: number;
  name: string;
  description: string | null;
  item_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface CollectionItemResponse {
  id: number;
  bill_id: string;
  notes: string | null;
  added_at: string | null;
}

export interface CollectionDetailResponse {
  id: number;
  name: string;
  description: string | null;
  items: CollectionItemResponse[];
  created_at: string | null;
  updated_at: string | null;
}

export interface CollectionListResponse {
  data: CollectionResponse[];
  meta: MetaResponse;
}

// --- Policy Workspaces ---

export interface PolicySectionResponse {
  id: string;
  section_key: string;
  heading: string;
  purpose: string | null;
  position: number;
  content_markdown: string;
  status: string;
  provenance: PolicySectionSourceResponse[];
  created_at: string | null;
  updated_at: string | null;
}

export interface PolicySectionSourceResponse {
  bill_id: string;
  identifier: string;
  title: string;
  jurisdiction_id: string;
  note: string | null;
}

export interface PolicyWorkspacePrecedentResponse {
  id: number;
  bill_id: string;
  position: number;
  added_at: string | null;
  identifier: string;
  title: string;
  jurisdiction_id: string;
  status: string | null;
}

export interface PolicyWorkspaceResponse {
  id: string;
  title: string;
  target_jurisdiction_id: string;
  drafting_template: string;
  goal_prompt: string | null;
  status: string;
  precedent_count: number;
  section_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface PolicyWorkspaceDetailResponse {
  id: string;
  title: string;
  target_jurisdiction_id: string;
  drafting_template: string;
  goal_prompt: string | null;
  status: string;
  precedents: PolicyWorkspacePrecedentResponse[];
  sections: PolicySectionResponse[];
  outline_drafting_notes: string[];
  outline_confidence: number | null;
  outline_generated_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PolicyWorkspaceListResponse {
  data: PolicyWorkspaceResponse[];
  meta: MetaResponse;
}

export interface PolicyGenerationResponse {
  id: string;
  workspace_id: string;
  section_id: string | null;
  action_type: string;
  instruction_text: string | null;
  selected_text: string | null;
  output_markdown: string;
  rationale: string;
  provenance: PolicySectionSourceResponse[];
  accepted: boolean;
  created_at: string | null;
}

export interface PolicyRevisionResponse {
  id: string;
  section_id: string;
  generation_id: string | null;
  change_source: string;
  content_markdown: string;
  created_at: string | null;
}

export interface PolicyHistoryResponse {
  revisions: PolicyRevisionResponse[];
}

// --- Chat ---

export interface ToolCallInfo {
  tool_name: string;
  arguments: Record<string, unknown>;
  result_summary: string | null;
}

export interface ChatMessageResponse {
  role: "user" | "assistant";
  content: string;
  tool_calls: ToolCallInfo[] | null;
  created_at: string | null;
}

export interface ChatResponse {
  conversation_id: string;
  message: ChatMessageResponse;
}

export interface ConversationResponse {
  id: string;
  title: string | null;
  messages: ChatMessageResponse[];
  created_at: string | null;
}

export interface ConversationListResponse {
  data: ConversationResponse[];
  meta: MetaResponse;
}

// --- Hearings ---

export interface HearingResponse {
  id: string;
  bill_id: string | null;
  committee_name: string;
  committee_code: string | null;
  chamber: string | null;
  title: string;
  hearing_date: string | null;
  location: string | null;
  url: string | null;
  congress: number | null;
  created_at: string | null;
  linked_bill_ids: string[];
}

export interface HearingListResponse {
  data: HearingResponse[];
  meta: MetaResponse;
}
