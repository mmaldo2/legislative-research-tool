/**
 * API client for the legislative research FastAPI backend.
 * All functions return typed responses matching the Pydantic schemas.
 */

import type {
  BillComparisonOutput,
  BillDetailResponse,
  BillListResponse,
  ChatResponse,
  CollectionDetailResponse,
  CollectionItemResponse,
  CollectionListResponse,
  CollectionResponse,
  ConstitutionalAnalysisOutput,
  ConversationListResponse,
  ConversationResponse,
  DiffusionOutput,
  HearingListResponse,
  HealthResponse,
  JurisdictionListResponse,
  JurisdictionStatsResponse,
  MLPredictionResponse,
  PatternDetectionOutput,
  PolicySectionResponse,
  PolicyWorkspaceDetailResponse,
  PolicyWorkspaceListResponse,
  PolicyWorkspacePrecedentResponse,
  PolicyWorkspaceResponse,
  PersonListResponse,
  PersonResponse,
  PersonStatsResponse,
  PersonVoteListResponse,
  PredictionOutput,
  ReportOutput,
  SearchResponse,
  SessionListResponse,
  SimilarBillsResponse,
  StatusResponse,
  VersionDiffOutput,
  VoteEventListResponse,
} from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const API_KEY = process.env.API_KEY ?? "";

class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

class RateLimitError extends Error {
  public readonly retryAfterSeconds: number | null;

  constructor(retryAfter: string | null) {
    const seconds = retryAfter ? parseInt(retryAfter, 10) : null;
    const validSeconds = seconds !== null && !Number.isNaN(seconds) ? seconds : null;
    super(
      validSeconds
        ? `Rate limited. Please retry after ${validSeconds} seconds.`
        : "Rate limited. Please wait a moment and try again.",
    );
    this.name = "RateLimitError";
    this.retryAfterSeconds = validSeconds;
    Object.setPrototypeOf(this, RateLimitError.prototype);
  }
}

interface FetchApiOptions extends Omit<RequestInit, "next"> {
  revalidate?: number | false;
}

function normalizeHeaders(headers?: HeadersInit): Record<string, string> {
  if (!headers) return {};
  if (headers instanceof Headers) {
    const result: Record<string, string> = {};
    headers.forEach((value, key) => {
      result[key] = value;
    });
    return result;
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return headers as Record<string, string>;
}

async function fetchApi<T>(path: string, init?: FetchApiOptions): Promise<T> {
  const url = `${API_BASE}${path}`;
  const { revalidate, ...rest } = init ?? {};
  const headers: Record<string, string> = {
    ...normalizeHeaders(rest.headers),
  };
  if (rest.body) {
    headers["Content-Type"] = "application/json";
  }
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }
  const res = await fetch(url, {
    ...rest,
    headers,
    ...(revalidate !== undefined ? { next: { revalidate } } : {}),
  });

  if (res.status === 429) {
    throw new RateLimitError(res.headers.get("Retry-After"));
  }

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    let message = body || res.statusText;
    if (body) {
      try {
        const parsed = JSON.parse(body) as { detail?: unknown };
        if (typeof parsed.detail === "string" && parsed.detail.trim()) {
          message = parsed.detail;
        }
      } catch {
        // Keep the raw body when the response is not JSON.
      }
    }
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

// --- Query string helper ---

function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== null && v !== undefined && v !== "",
  );
  if (entries.length === 0) return "";
  return "?" + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
}

// --- Bills ---

export async function listBills(params: {
  jurisdiction?: string;
  session?: string;
  status?: string;
  q?: string;
  subject?: string;
  sponsor?: string;
  page?: number;
  per_page?: number;
} = {}): Promise<BillListResponse> {
  return fetchApi<BillListResponse>(`/bills${qs(params)}`, { revalidate: 300 });
}

export async function getBill(billId: string): Promise<BillDetailResponse> {
  return fetchApi<BillDetailResponse>(
    `/bills/${encodeURIComponent(billId)}`,
    { revalidate: 300 },
  );
}

// --- Search ---

export async function searchBills(params: {
  q: string;
  jurisdiction?: string;
  mode?: "keyword" | "semantic" | "hybrid";
  page?: number;
  per_page?: number;
}): Promise<SearchResponse> {
  return fetchApi<SearchResponse>(`/search/bills${qs(params)}`, { revalidate: 60 });
}

// --- People ---

export async function listPeople(params: {
  jurisdiction?: string;
  party?: string;
  chamber?: string;
  q?: string;
  page?: number;
  per_page?: number;
} = {}): Promise<PersonListResponse> {
  return fetchApi<PersonListResponse>(`/people${qs(params)}`, { revalidate: 300 });
}

export async function getPerson(personId: string): Promise<PersonResponse> {
  return fetchApi<PersonResponse>(
    `/people/${encodeURIComponent(personId)}`,
    { revalidate: 300 },
  );
}

export async function getPersonVotes(
  personId: string,
  params: { page?: number; per_page?: number } = {},
): Promise<PersonVoteListResponse> {
  const query = qs(params);
  return fetchApi<PersonVoteListResponse>(
    `/people/${encodeURIComponent(personId)}/votes${query}`,
    { revalidate: 300 },
  );
}

export async function getPersonStats(personId: string): Promise<PersonStatsResponse> {
  return fetchApi<PersonStatsResponse>(
    `/people/${encodeURIComponent(personId)}/stats`,
    { revalidate: 300 },
  );
}

// --- Jurisdictions ---

export async function listJurisdictions(params: {
  classification?: string;
  page?: number;
  per_page?: number;
} = {}): Promise<JurisdictionListResponse> {
  return fetchApi<JurisdictionListResponse>(`/jurisdictions${qs(params)}`, { revalidate: 3600 });
}

export async function getJurisdictionStats(
  jurisdictionId: string,
): Promise<JurisdictionStatsResponse> {
  return fetchApi<JurisdictionStatsResponse>(
    `/jurisdictions/${encodeURIComponent(jurisdictionId)}/stats`,
    { revalidate: 300 },
  );
}

// --- Sessions ---

export async function listSessions(params: {
  jurisdiction?: string;
  page?: number;
  per_page?: number;
} = {}): Promise<SessionListResponse> {
  return fetchApi<SessionListResponse>(`/sessions${qs(params)}`, { revalidate: 3600 });
}

// --- Votes ---

export async function listVoteEvents(
  billId: string,
  params: {
    page?: number;
    per_page?: number;
  } = {},
): Promise<VoteEventListResponse> {
  const query = qs(params);
  return fetchApi<VoteEventListResponse>(
    `/bills/${encodeURIComponent(billId)}/votes${query}`,
    { revalidate: 300 },
  );
}

// --- Status ---

export async function getHealth(): Promise<HealthResponse> {
  return fetchApi<HealthResponse>("/status/health");
}

export async function getStatus(): Promise<StatusResponse> {
  return fetchApi<StatusResponse>("/status");
}

// --- Compare ---

export async function getSimilarBills(
  billId: string,
  params: { top_k?: number; min_score?: number; exclude_same_jurisdiction?: boolean } = {},
): Promise<SimilarBillsResponse> {
  const query = qs(params);
  return fetchApi<SimilarBillsResponse>(
    `/bills/${encodeURIComponent(billId)}/similar${query}`,
    { revalidate: 300 },
  );
}

export async function compareBills(
  billIdA: string,
  billIdB: string,
): Promise<BillComparisonOutput> {
  return fetchApi<BillComparisonOutput>("/analyze/compare", {
    method: "POST",
    body: JSON.stringify({ bill_id_a: billIdA, bill_id_b: billIdB }),
  });
}

// --- Intelligence Layer ---

export async function analyzeVersionDiff(
  billId: string,
  versionAId?: string,
  versionBId?: string,
  signal?: AbortSignal,
): Promise<VersionDiffOutput> {
  return fetchApi<VersionDiffOutput>("/analyze/version-diff", {
    method: "POST",
    body: JSON.stringify({
      bill_id: billId,
      version_a_id: versionAId ?? null,
      version_b_id: versionBId ?? null,
    }),
    signal,
  });
}

export async function analyzeConstitutional(
  billId: string,
  signal?: AbortSignal,
): Promise<ConstitutionalAnalysisOutput> {
  return fetchApi<ConstitutionalAnalysisOutput>("/analyze/constitutional", {
    method: "POST",
    body: JSON.stringify({ bill_id: billId }),
    signal,
  });
}

export async function analyzePatterns(
  billId: string,
  topK: number = 5,
  signal?: AbortSignal,
): Promise<PatternDetectionOutput> {
  return fetchApi<PatternDetectionOutput>("/analyze/patterns", {
    method: "POST",
    body: JSON.stringify({ bill_id: billId, top_k: topK }),
    signal,
  });
}

// --- Diffusion ---

export async function getDiffusion(
  billId: string,
  topK: number = 10,
  signal?: AbortSignal,
): Promise<DiffusionOutput> {
  const query = qs({ top_k: topK });
  return fetchApi<DiffusionOutput>(
    `/analyze/diffusion/${encodeURIComponent(billId)}${query}`,
    { signal },
  );
}

// --- Prediction ---

export async function predictOutcome(
  billId: string,
  signal?: AbortSignal,
): Promise<PredictionOutput> {
  return fetchApi<PredictionOutput>("/analyze/predict", {
    method: "POST",
    body: JSON.stringify({ bill_id: billId }),
    signal,
  });
}

// --- ML Prediction (fast, model-based) ---

export async function getBillPrediction(
  billId: string,
  signal?: AbortSignal,
): Promise<MLPredictionResponse> {
  return fetchApi<MLPredictionResponse>(`/bills/${billId}/prediction`, { signal });
}

// --- Reports ---

export async function generateReport(
  query: string,
  jurisdiction?: string,
  maxBills: number = 20,
  signal?: AbortSignal,
): Promise<ReportOutput> {
  return fetchApi<ReportOutput>("/reports/generate", {
    method: "POST",
    body: JSON.stringify({
      query,
      jurisdiction: jurisdiction ?? null,
      max_bills: maxBills,
    }),
    signal,
  });
}

// --- Collections ---

const CLIENT_ID_KEY = "legis-client-id";

function getClientId(): string {
  if (typeof window === "undefined") return "server";
  let id = localStorage.getItem(CLIENT_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(CLIENT_ID_KEY, id);
  }
  return id;
}

function clientHeaders(): Record<string, string> {
  return { "X-Client-Id": getClientId() };
}

export async function listCollections(params: {
  page?: number;
  per_page?: number;
} = {}): Promise<CollectionListResponse> {
  return fetchApi<CollectionListResponse>(`/collections${qs(params)}`, {
    headers: clientHeaders(),
    revalidate: false,
  });
}

export async function getCollection(id: number): Promise<CollectionDetailResponse> {
  return fetchApi<CollectionDetailResponse>(`/collections/${id}`, {
    headers: clientHeaders(),
    revalidate: false,
  });
}

export async function createCollection(
  name: string,
  description?: string,
): Promise<CollectionResponse> {
  return fetchApi<CollectionResponse>("/collections", {
    method: "POST",
    body: JSON.stringify({ name, description }),
    headers: clientHeaders(),
  });
}

export async function deleteCollection(id: number): Promise<void> {
  await fetchApi<void>(`/collections/${id}`, {
    method: "DELETE",
    headers: clientHeaders(),
  });
}

export async function addToCollection(
  collectionId: number,
  billId: string,
  notes?: string,
): Promise<CollectionItemResponse> {
  return fetchApi<CollectionItemResponse>(`/collections/${collectionId}/items`, {
    method: "POST",
    body: JSON.stringify({ bill_id: billId, notes }),
    headers: clientHeaders(),
  });
}

export async function removeFromCollection(
  collectionId: number,
  billId: string,
): Promise<void> {
  await fetchApi<void>(`/collections/${collectionId}/items/${encodeURIComponent(billId)}`, {
    method: "DELETE",
    headers: clientHeaders(),
  });
}

export async function updateCollectionItemNotes(
  collectionId: number,
  billId: string,
  notes: string | null,
): Promise<CollectionItemResponse> {
  return fetchApi<CollectionItemResponse>(
    `/collections/${collectionId}/items/${encodeURIComponent(billId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ notes }),
      headers: clientHeaders(),
    },
  );
}

// --- Policy Workspaces ---

export async function listPolicyWorkspaces(params: {
  page?: number;
  per_page?: number;
} = {}): Promise<PolicyWorkspaceListResponse> {
  return fetchApi<PolicyWorkspaceListResponse>(`/policy-workspaces${qs(params)}`, {
    headers: clientHeaders(),
    revalidate: false,
  });
}

export async function getPolicyWorkspace(id: string): Promise<PolicyWorkspaceDetailResponse> {
  return fetchApi<PolicyWorkspaceDetailResponse>(`/policy-workspaces/${encodeURIComponent(id)}`, {
    headers: clientHeaders(),
    revalidate: false,
  });
}

export async function createPolicyWorkspace(params: {
  title: string;
  target_jurisdiction_id: string;
  drafting_template: string;
  goal_prompt?: string;
}): Promise<PolicyWorkspaceResponse> {
  return fetchApi<PolicyWorkspaceResponse>("/policy-workspaces", {
    method: "POST",
    body: JSON.stringify(params),
    headers: clientHeaders(),
  });
}

export async function updatePolicyWorkspace(
  id: string,
  params: {
    title?: string;
    target_jurisdiction_id?: string;
    drafting_template?: string;
    goal_prompt?: string | null;
    status?: string;
  },
): Promise<PolicyWorkspaceResponse> {
  return fetchApi<PolicyWorkspaceResponse>(`/policy-workspaces/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(params),
    headers: clientHeaders(),
  });
}

export async function deletePolicyWorkspace(id: string): Promise<void> {
  await fetchApi<void>(`/policy-workspaces/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: clientHeaders(),
  });
}

export async function addPolicyWorkspacePrecedent(
  workspaceId: string,
  billId: string,
  position?: number,
): Promise<PolicyWorkspacePrecedentResponse> {
  return fetchApi<PolicyWorkspacePrecedentResponse>(
    `/policy-workspaces/${encodeURIComponent(workspaceId)}/precedents`,
    {
      method: "POST",
      body: JSON.stringify({ bill_id: billId, position }),
      headers: clientHeaders(),
    },
  );
}

export async function removePolicyWorkspacePrecedent(
  workspaceId: string,
  billId: string,
): Promise<void> {
  await fetchApi<void>(
    `/policy-workspaces/${encodeURIComponent(workspaceId)}/precedents/${encodeURIComponent(billId)}`,
    {
      method: "DELETE",
      headers: clientHeaders(),
    },
  );
}

export async function generatePolicyWorkspaceOutline(
  workspaceId: string,
): Promise<PolicyWorkspaceDetailResponse> {
  return fetchApi<PolicyWorkspaceDetailResponse>(
    `/policy-workspaces/${encodeURIComponent(workspaceId)}/outline/generate`,
    {
      method: "POST",
      headers: clientHeaders(),
    },
  );
}

export async function updatePolicyWorkspaceSection(
  workspaceId: string,
  sectionId: string,
  params: {
    heading?: string;
    purpose?: string | null;
  },
): Promise<PolicySectionResponse> {
  return fetchApi<PolicySectionResponse>(
    `/policy-workspaces/${encodeURIComponent(workspaceId)}/sections/${encodeURIComponent(sectionId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(params),
      headers: clientHeaders(),
    },
  );
}

// --- Chat ---

export async function sendChatMessage(
  message: string,
  conversationId?: string,
): Promise<ChatResponse> {
  return fetchApi<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, conversation_id: conversationId }),
    headers: clientHeaders(),
  });
}

export async function listConversations(params: {
  page?: number;
  per_page?: number;
} = {}): Promise<ConversationListResponse> {
  return fetchApi<ConversationListResponse>(`/conversations${qs(params)}`, {
    headers: clientHeaders(),
    revalidate: false,
  });
}

export async function getConversation(id: string): Promise<ConversationResponse> {
  return fetchApi<ConversationResponse>(`/conversations/${encodeURIComponent(id)}`, {
    headers: clientHeaders(),
    revalidate: false,
  });
}

// --- Export ---

export function getExportCsvUrl(params: {
  bill_ids?: string;
  jurisdiction?: string;
  status?: string;
  q?: string;
  include_summary?: boolean;
}): string {
  return `${API_BASE}/export/bills/csv${qs(params)}`;
}

export function getBillBriefUrl(billId: string): string {
  return `${API_BASE}/export/bills/${encodeURIComponent(billId)}/brief`;
}

// --- Hearings ---

export async function listBillHearings(
  billId: string,
  params: { page?: number; per_page?: number } = {},
): Promise<HearingListResponse> {
  const query = qs(params);
  return fetchApi<HearingListResponse>(
    `/bills/${encodeURIComponent(billId)}/hearings${query}`,
    { revalidate: 300 },
  );
}

export async function listHearings(params: {
  committee?: string;
  chamber?: string;
  congress?: number;
  bill_id?: string;
  date_from?: string;
  date_to?: string;
  q?: string;
  page?: number;
  per_page?: number;
} = {}): Promise<HearingListResponse> {
  return fetchApi<HearingListResponse>(`/hearings${qs(params)}`, { revalidate: 300 });
}

export { ApiError, RateLimitError };
