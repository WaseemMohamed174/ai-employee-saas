/**
 * Data service — upload and list store data via the dashboard API.
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type DataItem = {
  id: number;
  item_id: string;
  content_preview: string;
  source: string;
  uploaded_at: string;
};

export type UploadResult = {
  uploaded_count: number;
  total_bytes: number;
  upload_log_id: number;
};

export type DataList = {
  items: DataItem[];
  total: number;
  page: number;
  page_size: number;
};

export type UploadLog = {
  id: number;
  source: string;
  item_count: number;
  file_size_bytes: number;
  uploaded_by_user_id: number | null;
  uploaded_at: string;
};

export type UploadLogList = {
  logs: UploadLog[];
  total: number;
  page: number;
  page_size: number;
};

// ============== API CALLS ==============

export const dataService = {
  /** POST /api/v1/dashboard/database/upload — upload items via dashboard (JWT auth). */
  upload: (items: { id: string; content: string }[]) =>
    request<UploadResult>("/dashboard/database/upload", {
      method: "POST",
      body: { items, source: "dashboard" },
    }),

  /** GET /api/v1/dashboard/database — list data items (paginated). */
  list: (page: number = 1, pageSize: number = 20) =>
    request<DataList>(`/dashboard/database?page=${page}&page_size=${pageSize}`),

  /** GET /api/v1/dashboard/database/logs — list upload logs (audit trail). */
  listLogs: (page: number = 1, pageSize: number = 10) =>
    request<UploadLogList>(`/dashboard/database/logs?page=${page}&page_size=${pageSize}`),
};
