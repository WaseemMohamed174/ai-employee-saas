/**
 * API client — thin wrapper around fetch that:
 * - prefixes /api/v1 to all paths
 * - injects the Bearer token from localStorage if present
 * - parses the unified { ok, data, error } response
 * - throws an Error with the error message if ok === false
 */

const API_PREFIX = "/api/v1";
const TOKEN_KEY = "shop_assistant_token";

// ============== TOKEN STORAGE ==============

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* ignore quota / privacy errors */
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

// ============== ERROR TYPE ==============

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

// ============== REQUEST HELPER ==============

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  token?: string | null;
  /** Skip auth header even if a token is in localStorage (for login/signup). */
  noAuth?: boolean;
};

export async function request<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const url = path.startsWith("/api/") ? path : `${API_PREFIX}${path}`;
  const token = opts.token ?? (opts.noAuth ? null : getToken());

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  let payload: { ok?: boolean; data?: T; error?: { code: string; message: string } } = {};
  try {
    payload = await res.json();
  } catch {
    payload = {};
  }

  if (!payload.ok) {
    const err = payload.error ?? { code: "unknown", message: `HTTP ${res.status}` };
    throw new ApiError(err.code, err.message, res.status);
  }
  return payload.data as T;
}
