/**
 * API key service — create, list, revoke keys.
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type ApiKey = {
  id: number;
  name: string;
  last_used_at: string | null;
  created_at: string;
  revoked_at: string | null;
  key?: string | null; // Only present on creation
};

// ============== API CALLS ==============

export const apiKeyService = {
  create: (name: string) =>
    request<ApiKey>("/api-keys", { method: "POST", body: { name } }),

  list: () => request<{ keys: ApiKey[] }>("/api-keys"),

  revoke: (keyId: number) =>
    request<{ revoked: boolean; key_id: number }>(`/api-keys/${keyId}`, { method: "DELETE" }),
};
