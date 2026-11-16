/**
 * Persona service — the store-owner assistant persona page (F11, FR-16).
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type PersonaOption = {
  id: number;
  code: string;
  name: string;
  description: string;
};

export type PersonaPage = {
  current_persona: PersonaOption | null;
  using_default: boolean;
  /** The persona the chats actually use now: the choice, or the platform default. */
  effective_persona: PersonaOption | null;
  options: PersonaOption[];
};

// ============== API CALLS ==============

export const personaService = {
  /** GET /api/v1/dashboard/persona — current choice + the 4-option catalog (JWT auth). */
  get: () => request<PersonaPage>("/dashboard/persona"),

  /** PUT /api/v1/dashboard/persona — persist the picked persona (422 unknown id).
   *  NOTE: apiClient.request stringifies `body` itself — always pass a plain object. */
  update: (personaId: number) =>
    request<{ persona: PersonaOption }>("/dashboard/persona", {
      method: "PUT",
      body: { persona_id: personaId },
    }),
};
