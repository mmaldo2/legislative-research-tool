/**
 * API client for the legislative research FastAPI backend.
 * All functions return typed responses matching the Pydantic schemas.
 */

import type {
  BillDetailResponse,
  BillListResponse,
  HealthResponse,
  JurisdictionListResponse,
  PersonListResponse,
  PersonResponse,
  SearchResponse,
  SessionListResponse,
  StatusResponse,
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

async function fetchApi<T>(path: string, init?: FetchApiOptions): Promise<T> {
  const url = `${API_BASE}${path}`;
  const { revalidate, ...rest } = init ?? {};
  const headers: Record<string, string> = {
    ...(rest.headers as Record<string, string>),
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
    throw new ApiError(res.status, body || res.statusText);
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

// --- Jurisdictions ---

export async function listJurisdictions(params: {
  classification?: string;
  page?: number;
  per_page?: number;
} = {}): Promise<JurisdictionListResponse> {
  return fetchApi<JurisdictionListResponse>(`/jurisdictions${qs(params)}`, { revalidate: 3600 });
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

export { ApiError, RateLimitError };
