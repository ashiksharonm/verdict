import { API_URL } from "./config";

export type CheckResult = { flagged: boolean; score: number; threshold: number };
export type CheckResponse = {
  id: string;
  model_version: string;
  results: Record<string, CheckResult>;
  latency_ms: number;
};
export type CheckRequest = { text: string; checks: string[]; context?: string };

export type PlaygroundOutcome =
  | { kind: "ok"; data: CheckResponse; attempts: number }
  | { kind: "rate_limited"; retryAfter: number | null; message: string }
  | { kind: "error"; status: number | null; message: string };

export type PlaygroundOptions = {
  baseUrl?: string;
  token?: string;
  fetchImpl?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
  /** Called before each wait while the API is asleep / cold-starting. */
  onWarming?: (info: { attempt: number; waitMs: number; elapsedMs: number }) => void;
  signal?: AbortSignal;
  maxWaitMs?: number;
};

const COLD_STATUSES = new Set([502, 503, 504, 520, 521, 522, 523, 524]);
const defaultSleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/** Backoff schedule: 2s, 4s, 6s, 8s, then 10s steps. */
export function backoffMs(attempt: number): number {
  return Math.min(10_000, 2_000 * attempt);
}

export function parseRetryAfter(value: string | null): number | null {
  if (!value) return null;
  const n = Number(value);
  if (Number.isFinite(n) && n >= 0) return Math.ceil(n);
  const t = Date.parse(value);
  return Number.isNaN(t) ? null : Math.max(0, Math.ceil((t - Date.now()) / 1000));
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const d = body?.detail ?? body?.error ?? body?.message;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => x?.msg ?? JSON.stringify(x)).join("; ");
    if (d) return JSON.stringify(d);
  } catch {
    /* not JSON */
  }
  return res.statusText || `HTTP ${res.status}`;
}

function isCheckResponse(x: unknown): x is CheckResponse {
  const r = x as CheckResponse;
  return !!r && typeof r === "object" && typeof r.results === "object" && r.results !== null && typeof r.model_version === "string";
}

/** POST /v1/playground/check with cold-start retries (up to ~60 s) and 429 handling. */
export async function playgroundCheck(req: CheckRequest, opts: PlaygroundOptions = {}): Promise<PlaygroundOutcome> {
  const doFetch = opts.fetchImpl ?? fetch;
  const sleep = opts.sleep ?? defaultSleep;
  const now = opts.now ?? Date.now;
  const maxWait = opts.maxWaitMs ?? 60_000;
  const url = `${opts.baseUrl ?? API_URL}/v1/playground/check`;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.token) headers["X-Turnstile-Token"] = opts.token;
  const body = JSON.stringify({ text: req.text, checks: req.checks, ...(req.context ? { context: req.context } : {}) });

  const start = now();
  let attempt = 0;
  let last: { status: number | null; message: string } = { status: null, message: "Could not reach the API." };
  for (;;) {
    attempt += 1;
    let cold = false;
    try {
      const res = await doFetch(url, { method: "POST", headers, body, signal: opts.signal });
      if (res.ok) {
        const data: unknown = await res.json().catch(() => null);
        if (isCheckResponse(data)) return { kind: "ok", data, attempts: attempt };
        // A sleeping Space can answer 200 with an HTML placeholder page.
        cold = true;
        last = { status: res.status, message: "The API returned an unexpected response." };
      } else if (res.status === 429) {
        const retryAfter = parseRetryAfter(res.headers.get("Retry-After"));
        return {
          kind: "rate_limited",
          retryAfter,
          message: retryAfter != null ? `Rate limit reached. Try again in ${retryAfter}s.` : "Rate limit reached. Try again shortly.",
        };
      } else if (COLD_STATUSES.has(res.status)) {
        cold = true;
        last = { status: res.status, message: "The API is waking up." };
      } else {
        return { kind: "error", status: res.status, message: await errorMessage(res) };
      }
    } catch (e) {
      if (opts.signal?.aborted) return { kind: "error", status: null, message: "Cancelled." };
      cold = true; // network failure: a sleeping Space often refuses or resets the connection
      last = { status: null, message: e instanceof Error ? e.message : "Network error." };
    }
    if (!cold) break;
    const elapsed = now() - start;
    const wait = backoffMs(attempt);
    if (elapsed + wait > maxWait) {
      return { kind: "error", status: last.status, message: `The API did not wake up within ${Math.round(maxWait / 1000)} s (${last.message}). Try again in a minute.` };
    }
    opts.onWarming?.({ attempt, waitMs: wait, elapsedMs: elapsed });
    await sleep(wait);
  }
  return { kind: "error", status: last.status, message: last.message };
}

/* ---------- authenticated key management ---------- */

export type ApiKey = { id: string; prefix: string; name: string; created_at: string; last_used_at?: string | null; revoked_at?: string | null };
export type NewApiKey = ApiKey & { key: string };
export type Usage = { days: { day: string; count: number }[]; month_total: number; monthly_quota: number };

/** GET /v1/usage returns the monthly limit as `quota`; normalise so the dashboard never reads undefined. */
export function normaliseUsage(raw: Partial<Usage> & { quota?: number }): Usage {
  return {
    days: Array.isArray(raw.days) ? raw.days : [],
    month_total: Number(raw.month_total ?? 0),
    monthly_quota: Number(raw.monthly_quota ?? raw.quota ?? 0),
  };
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function authed<T>(path: string, token: string, init: RequestInit = {}, fetchImpl: typeof fetch = fetch): Promise<T> {
  const res = await fetchImpl(`${API_URL}${path}`, {
    ...init,
    headers: { ...(init.body ? { "Content-Type": "application/json" } : {}), Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const listKeys = (token: string) => authed<ApiKey[] | { keys: ApiKey[] }>("/v1/keys", token).then((r) => (Array.isArray(r) ? r : r.keys ?? []));
export const createKey = (token: string, name: string) => authed<NewApiKey>("/v1/keys", token, { method: "POST", body: JSON.stringify({ name }) });
export const revokeKey = (token: string, id: string) => authed<void>(`/v1/keys/${encodeURIComponent(id)}`, token, { method: "DELETE" });
export const getUsage = (token: string) => authed<Partial<Usage> & { quota?: number }>("/v1/usage", token).then(normaliseUsage);
