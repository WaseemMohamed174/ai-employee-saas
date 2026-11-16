/**
 * Complaints service — dashboard complaints list for the store owner (F07).
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type ComplaintListItem = {
  analysis_id: number;
  message_id: number;
  conversation_id: number;
  customer_external_id: string;
  message_excerpt: string;
  customer_message: string | null;
  sentiment: string | null;
  severity: string | null;
  sent_at: string;
};

export type ComplaintList = {
  items: ComplaintListItem[];
  total: number;
  page: number;
  page_size: number;
};

// ============== API CALLS ==============

export const complaintsService = {
  /** GET /api/v1/dashboard/complaints — paginated complaints with optional sentiment filter (JWT auth). */
  list: (page: number = 1, pageSize: number = 20, sentiment: string = "all") => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (sentiment !== "all") params.set("sentiment", sentiment);
    return request<ComplaintList>(`/dashboard/complaints?${params.toString()}`);
  },
};
