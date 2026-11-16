/**
 * Alerts service — dashboard alerts list + dismiss for the store owner (F10).
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type AlertType = "complaint_spike" | "new_violation" | "token_near_limit" | "transfer_pending";

export type AlertListItem = {
  id: number;
  type: AlertType | string;
  severity: "info" | "warning" | "critical" | string;
  message: string;
  payload: string | null;
  created_at: string;
  dismissed_at: string | null;
};

export type AlertList = {
  items: AlertListItem[];
  total: number;
  page: number;
  page_size: number;
};

// ============== API CALLS ==============

export const alertsService = {
  /** GET /api/v1/dashboard/alerts — paginated alerts with optional type + status filters (JWT auth). */
  list: (page: number = 1, pageSize: number = 20, type: string = "all", status: string = "all") => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (type !== "all") params.set("type", type);
    if (status !== "all") params.set("status", status);
    return request<AlertList>(`/dashboard/alerts?${params.toString()}`);
  },

  /** POST /api/v1/dashboard/alerts/{id}/dismiss — stamp dismissed_at (lifecycle 6.3). */
  dismiss: (alertId: number) =>
    request<{ alert: AlertListItem }>(`/dashboard/alerts/${alertId}/dismiss`, {
      method: "POST",
    }),
};
