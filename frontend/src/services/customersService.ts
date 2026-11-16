/**
 * Customers service — dashboard customers list + unban for the store owner (F09).
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type CustomerCaseStatus = "active" | "analyzing" | "warned" | "banned" | "transferred";

export type CustomerListItem = {
  id: number;
  external_id: string;
  case_status: CustomerCaseStatus | string;
  first_seen_at: string;
  banned_at: string | null;
  banned_reason: string | null;
  violation_count: number;
};

export type CustomerList = {
  items: CustomerListItem[];
  total: number;
  page: number;
  page_size: number;
};

// ============== API CALLS ==============

export const customersService = {
  /** GET /api/v1/dashboard/customers — paginated chat customers with optional case_status filter (JWT auth). */
  list: (page: number = 1, pageSize: number = 20, caseStatus: string = "all") => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (caseStatus !== "all") params.set("case_status", caseStatus);
    return request<CustomerList>(`/dashboard/customers?${params.toString()}`);
  },

  /** POST /api/v1/dashboard/customers/{id}/unban — lift the ban (banned → active, FR-15). */
  unban: (customerId: number) =>
    request<{ customer: CustomerListItem }>(`/dashboard/customers/${customerId}/unban`, {
      method: "POST",
    }),
};
