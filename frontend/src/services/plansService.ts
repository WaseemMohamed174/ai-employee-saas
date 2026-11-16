import { request } from "./apiClient";

// ============== PLANS & USAGE SERVICE (F14, FR-03 + FR-13) ==============
// The only door between the Plans & Usage page and the API (rule 6.4 — no fetch in components).
// The server nests the full plan (limits + name + price) inside every subscription row,
// so the responses here map 1:1 to the page's state — no client-side catalog needed.

export interface PlanLimits {
  plan_code: string;
  plan_name: string;
  plan_is_trial: boolean;
  data_limit_kb: number;
  token_limit_month: number;
  conversation_limit_month: number;
  price_usd_cents: number;
}

export interface SubscriptionInfo {
  id: number;
  status: string;
  started_at: string;
  ends_at: string | null;
  canceled_at: string | null;
  plan: PlanLimits;
}

export interface UsageStats {
  tokens_used: number;
  conversations_used: number;
  data_used_kb: number;
  plan: PlanLimits;
}

export interface PlanCatalogItem {
  id: number;
  code: string;
  name: string;
  data_limit_kb: number;
  token_limit_month: number;
  conversation_limit_month: number;
  price_usd_cents: number;
  price_usd_display: string;
  is_trial: boolean;
}

export interface PlansOverview {
  current: SubscriptionInfo;
  available: PlanCatalogItem[];
  usage: UsageStats;
}

export interface SubscriptionChangeResult {
  subscription: SubscriptionInfo;
  checkout_url: string;
  mode: string;
}

export const plansService = {
  /** GET /api/v1/dashboard/plans — current subscription + paid catalog + usage (contract 8.4). */
  getOverview: () => request<PlansOverview>("/dashboard/plans"),

  /** POST /api/v1/subscriptions — mock checkout: immediate plan switch (contract 8.2). */
  changeSubscription: (planCode: string) =>
    request<SubscriptionChangeResult>("/subscriptions", {
      method: "POST",
      body: { plan_code: planCode },
    }),
};
