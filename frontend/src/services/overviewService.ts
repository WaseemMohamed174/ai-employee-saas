/**
 * Overview service — the dashboard Overview page aggregates (F15).
 * GET /api/v1/dashboard/overview → stats + uploads_per_day + items_by_source
 * + keys_by_status + recent_uploads/conversations/alerts (one GET renders everything).
 */
import { request } from "./apiClient";

export interface OverviewStats {
  items_total: number;
  bytes_total: number;
  uploads_count: number;
  keys_active: number;
  keys_revoked: number;
  conversations_total: number;
  complaints_total: number;
  alerts_active: number;
}

export interface UploadDayPoint {
  day: string;
  items: number;
}

export interface RecentUpload {
  id: number;
  source: string;
  item_count: number;
  file_size_bytes: number;
  uploaded_at: string;
}

export interface RecentConversation {
  id: number;
  status: string;
  started_at: string;
}

export interface RecentAlert {
  id: number;
  type: string;
  severity: string;
  created_at: string;
}

export interface OverviewData {
  stats: OverviewStats;
  uploads_per_day: UploadDayPoint[];
  items_by_source: Record<string, number>;
  keys_by_status: Record<string, number>;
  recent_uploads: RecentUpload[];
  recent_conversations: RecentConversation[];
  recent_alerts: RecentAlert[];
}

export const overviewService = {
  /** Fetches the whole overview payload (Owner JWT required by the backend). */
  getOverview(): Promise<OverviewData> {
    return request<OverviewData>("/dashboard/overview", { noAuth: false });
  },
};
