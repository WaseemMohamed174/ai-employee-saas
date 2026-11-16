/**
 * System status service — the store-owner service health page (F12, FR-13).
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type ServiceStatus = {
  id: string;
  name: string;
  /** "operational" or "degraded" — degraded = running in a safe fallback mode. */
  status: string;
  detail: string;
  /** Only for process-backed services (the REST API itself). */
  uptime_seconds: number | null;
};

export type SystemStatus = {
  /** "operational" only when EVERY service is operational, else "degraded". */
  overall: string;
  operational_count: number;
  degraded_count: number;
  version: string;
  /** The API process uptime in seconds (live, not synthetic). */
  uptime_seconds: number;
  generated_at: string;
  services: ServiceStatus[];
};

// ============== API CALLS ==============

export const systemStatusService = {
  /** GET /api/v1/dashboard/system-status — the whole platform health (JWT auth). */
  get: () => request<SystemStatus>("/dashboard/system-status"),
};

// ============== HELPERS ==============

/** Renders seconds as a compact human uptime: 90 → "1m 30s", 7200 → "2h", 93720 → "1d 2h". */
export function formatUptime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const days = Math.floor(s / 86400);
  const hours = Math.floor((s % 86400) / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  const parts: string[] = [];
  if (days) parts.push(`${days}d`);
  if (hours) parts.push(`${hours}h`);
  if (minutes) parts.push(`${minutes}m`);
  if (!days && !hours) parts.push(`${secs}s`); // short uptimes show seconds; long ones stay compact
  return parts.join(" ");
}
