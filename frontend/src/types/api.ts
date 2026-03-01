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
}

export interface PersonListResponse {
  data: PersonResponse[];
  meta: MetaResponse;
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

export interface TopicClassificationOutput {
  primary_topic: string;
  secondary_topics: string[];
  policy_area: string;
  confidence: number;
}

export interface AnalysisResponse {
  id: number;
  bill_id: string;
  analysis_type: string;
  result: Record<string, unknown>;
  model_used: string;
  prompt_version: string;
  confidence: number | null;
  tokens_input: number | null;
  tokens_output: number | null;
  cost_usd: number | null;
  created_at: string | null;
}

export interface AnalysisListResponse {
  data: AnalysisResponse[];
  meta: MetaResponse;
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
