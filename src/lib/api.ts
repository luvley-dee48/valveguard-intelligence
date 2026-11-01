/**
 * Typed client for the ValveGuard API (FastAPI backend in app/).
 *
 * In development the Vite dev server proxies /api to http://127.0.0.1:8000 (see vite.config.ts),
 * so the browser only ever talks to its own origin. Set VITE_API_BASE if the API lives elsewhere.
 */
export type Priority = "normal" | "inspect_soon" | "urgent_review" | "verify_sensor";
export type Likelihood = "high" | "medium" | "low";
export type Urgency = "immediate" | "within_24h" | "this_week" | "monitor";

export interface Valve {
  id: number;
  tag: string;
  name: string;
  type: string;
  area: string;
  serial: string;
  position_pct: number;
  command_pct: number;
  response_ms: number;
  baseline_response_ms: number;
  pressure_bar: number | null;
  temperature_c: number | null;
  vibration_mm_s: number | null;
  response_ratio: number | null;
  position_deviation_pct: number;
  health: number;
  priority: Priority;
  finding: string;
  created_at: string;
  updated_at: string;
  trend?: number[];
}

export interface Finding {
  rule: string;
  level: string;
  title: string;
  detail: string;
}

export interface ValveDetail extends Valve {
  findings: Finding[];
  thresholds: Record<string, number>;
}

export interface Diagnosis {
  summary: string;
  likely_explanations: { cause: string; likelihood: Likelihood }[];
  recommended_first_action: string;
  next_checks: string[];
  data_gaps: string[];
  urgency: Urgency;
  confidence: number;
}

export interface Report {
  id: number;
  valve_id: number;
  valve_tag: string | null;
  evidence: Record<string, unknown>;
  analysis: Diagnosis;
  source: "gemini" | "rules";
  model: string | null;
  error: string | null;
  latency_ms: number;
  review: "pending" | "accepted" | "needs_data" | "false_positive";
  review_note: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface AiCall {
  id: number;
  ts: string;
  kind: string;
  valve_tag: string | null;
  model: string | null;
  api_model_version: string | null;
  source: string;
  error: string | null;
  latency_ms: number;
  response_preview: string;
}

export interface AiStatus {
  configured: boolean;
  model: string;
  json_mode: boolean;
  endpoint: string;
  provider: string;
  fallback: string;
  calls_per_hour_per_user: number;
  documented_models: string[];
}

export interface DemoSession {
  token: string;
  user: { id: number; name: string; role: string; org: { id: number; name: string } };
  valves: number;
}

const ENV = (import.meta as unknown as { env?: Record<string, string | undefined> }).env ?? {};
const BASE = (ENV["VITE_API_BASE"] ?? "").replace(/\/$/, "");
const TOKEN_KEY = "vg_demo_token";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        "content-type": "application/json",
        ...(token ? { authorization: `Bearer ${token}` } : {}),
        ...(init.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError("The ValveGuard API is not reachable. Start it with `bash run.sh` (port 8000).", 0);
  }
  if (!res.ok) {
    let message = `Request failed (HTTP ${res.status}).`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      /* keep the status message */
    }
    throw new ApiError(message, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function getStoredToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function storeToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage can be blocked; the page still works for this visit */
  }
}

export const api = {
  aiStatus: () => request<AiStatus>("/api/demo/ai-status"),
  createDemoSession: () => request<DemoSession>("/api/demo/session", { method: "POST" }),
  valves: (token: string) => request<Valve[]>("/api/valves", {}, token),
  valve: (token: string, id: number) => request<ValveDetail>(`/api/valves/${id}`, {}, token),
  runReport: (token: string, id: number) =>
    request<Report>(`/api/valves/${id}/reports`, { method: "POST" }, token),
  reviewReport: (token: string, reportId: number, decision: Report["review"], note = "") =>
    request<Report>(`/api/reports/${reportId}/review`, {
      method: "POST",
      body: JSON.stringify({ decision, note }),
    }, token),
  aiCalls: (token: string) => request<AiCall[]>("/api/system/ai-calls?limit=6", {}, token),
};

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : "Something went wrong.";
}
