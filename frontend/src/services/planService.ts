/**
 * Plan service — fetches the public plan catalog.
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type Plan = {
  id: number;
  code: string;
  name: string;
  data_limit_kb: number;
  token_limit_month: number;
  conversation_limit_month: number;
  price_usd_cents: number;
  price_usd_display: string;
  is_trial: boolean;
};

// ============== API CALLS ==============

export const planService = {
  /** GET /api/v1/plans — public, no auth needed. Returns the plan catalog. */
  list: () => request<{ plans: Plan[] }>("/plans", { noAuth: true }),
};
