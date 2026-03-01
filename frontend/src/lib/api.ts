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

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

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
  return fetchApi<BillListResponse>(`/bills${qs(params)}`);
}

export async function getBill(billId: string): Promise<BillDetailResponse> {
  return fetchApi<BillDetailResponse>(`/bills/${encodeURIComponent(billId)}`);
}

// --- Search ---

export async function searchBills(params: {
  q: string;
  jurisdiction?: string;
  mode?: "keyword" | "semantic" | "hybrid";
  page?: number;
  per_page?: number;
}): Promise<SearchResponse> {
  return fetchApi<SearchResponse>(`/search/bills${qs(params)}`);
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
  return fetchApi<PersonListResponse>(`/people${qs(params)}`);
}

export async function getPerson(personId: string): Promise<PersonResponse> {
  return fetchApi<PersonResponse>(`/people/${encodeURIComponent(personId)}`);
}

// --- Jurisdictions ---

export async function listJurisdictions(params: {
  classification?: string;
  page?: number;
  per_page?: number;
} = {}): Promise<JurisdictionListResponse> {
  return fetchApi<JurisdictionListResponse>(`/jurisdictions${qs(params)}`);
}

// --- Sessions ---

export async function listSessions(params: {
  jurisdiction?: string;
  page?: number;
  per_page?: number;
} = {}): Promise<SessionListResponse> {
  return fetchApi<SessionListResponse>(`/sessions${qs(params)}`);
}

// --- Votes ---

export async function listVoteEvents(params: {
  bill_id?: string;
  page?: number;
  per_page?: number;
} = {}): Promise<VoteEventListResponse> {
  return fetchApi<VoteEventListResponse>(`/votes${qs(params)}`);
}

// --- Status ---

export async function getHealth(): Promise<HealthResponse> {
  return fetchApi<HealthResponse>("/status/health");
}

export async function getStatus(): Promise<StatusResponse> {
  return fetchApi<StatusResponse>("/status");
}

export { ApiError };
