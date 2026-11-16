/**
 * Health service — the unauthenticated backend liveness probe (GET /api/health).
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type BackendHealth = {
  status: string;
  service: string;
  version: string;
  time: string;
};

// ============== API CALLS ==============

export const healthService = {
  /** GET /api/health — returns the health data, or null while the backend is not reachable. */
  get: async (): Promise<BackendHealth | null> => {
    try {
      return await request<BackendHealth>("/api/health", { noAuth: true });
    } catch {
      return null;
    }
  },
};
