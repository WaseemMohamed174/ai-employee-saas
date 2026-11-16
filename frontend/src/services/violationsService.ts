/**
 * Violations service — dashboard violations list + policy management for the store owner (F08).
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type ViolationAction = "warning" | "temp_ban" | "perma_ban";

export type ViolationListItem = {
  id: number;
  customer_id: number;
  customer_external_id: string;
  action: ViolationAction | string;
  reason: string | null;
  created_at: string;
  expires_at: string | null;
};

export type ViolationList = {
  items: ViolationListItem[];
  total: number;
  page: number;
  page_size: number;
};

export type ViolationPolicy = {
  id: number;
  action: ViolationAction;
  threshold_count: number;
  threshold_window_hours: number;
  auto_apply: boolean;
  created_at: string;
};

export type PolicyPayload = {
  action: ViolationAction;
  threshold_count: number;
  threshold_window_hours: number;
  auto_apply: boolean;
};

// ============== API CALLS ==============

export const violationsService = {
  /** GET /api/v1/dashboard/violations — paginated violations with optional action filter (JWT auth). */
  list: (page: number = 1, pageSize: number = 20, action: string = "all") => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (action !== "all") params.set("action", action);
    return request<ViolationList>(`/dashboard/violations?${params.toString()}`);
  },

  /** GET /api/v1/dashboard/violations/policies — the store's escalation policies (JWT auth). */
  listPolicies: () => request<{ items: ViolationPolicy[] }>("/dashboard/violations/policies"),

  /** POST /api/v1/dashboard/violations/policy — create or update one policy (same action = upsert). */
  savePolicy: (payload: PolicyPayload) =>
    request<{ policy: ViolationPolicy }>("/dashboard/violations/policy", {
      method: "POST",
      body: payload,
    }),
};
