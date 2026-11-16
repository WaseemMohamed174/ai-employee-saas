/**
 * Conversations service — dashboard list + detail for the store owner (F06).
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type ConversationListItem = {
  id: number;
  status: string;
  customer_external_id: string;
  case_status: string;
  messages_count: number;
  last_message_preview: string | null;
  started_at: string;
  last_message_at: string | null;
};

export type ConversationList = {
  items: ConversationListItem[];
  total: number;
  page: number;
  page_size: number;
};

export type MessageAnalysis = {
  sentiment: string;
  is_complaint: boolean;
  is_violation: boolean;
  violation_type: string | null;
  severity: string | null;
};

export type ConversationMessage = {
  id: number;
  role: string;
  content: string;
  sent_at: string;
  analysis: MessageAnalysis | null;
};

export type ConversationDetail = {
  conversation: ConversationListItem;
  messages: ConversationMessage[];
};

// ============== API CALLS ==============

export const conversationsService = {
  /** GET /api/v1/dashboard/conversations — paginated list with optional status filter (JWT auth). */
  list: (page: number = 1, pageSize: number = 20, status: string = "all") => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status !== "all") params.set("status", status);
    return request<ConversationList>(`/dashboard/conversations?${params.toString()}`);
  },

  /** GET /api/v1/dashboard/conversations/:id — one conversation with messages + analyses. */
  get: (id: number) => request<ConversationDetail>(`/dashboard/conversations/${id}`),
};
