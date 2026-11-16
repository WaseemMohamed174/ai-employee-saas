/**
 * Store service — typed wrappers for /api/v1/stores and /api/v1/usage.
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type PlanLimits = {
  plan_code: string;
  plan_name: string;
  plan_is_trial: boolean;
  data_limit_kb: number;
  token_limit_month: number;
  conversation_limit_month: number;
  price_usd_cents: number;
};

export type Store = {
  id: number;
  slug: string;
  name: string;
  owner_user_id: number;
  default_persona_id: number | null;
  created_at: string;
};

export type Subscription = {
  id: number;
  status: string;
  started_at: string;
  ends_at: string | null;
  canceled_at: string | null;
  plan: PlanLimits;
};

export type Usage = {
  tokens_used: number;
  conversations_used: number;
  data_used_kb: number;
  plan: PlanLimits;
};

export type StoreWithSubscription = {
  store: Store;
  subscription: Subscription;
  usage: Usage;
};

// ============== API CALLS ==============

export const storeService = {
  createStore: (slug: string, name: string) =>
    request<StoreWithSubscription>("/stores", { method: "POST", body: { slug, name } }),

  // `data: null` when the account has no store yet (the API answers 200 on purpose
  // — a 404 probe on every dashboard visit used to paint the console red).
  getMyStore: () => request<StoreWithSubscription | null>("/stores/me"),

  getUsage: () => request<Usage>("/usage"),
};
