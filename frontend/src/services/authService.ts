/**
 * Auth service — typed wrappers around the /api/v1/auth/* endpoints.
 */

import { request } from "./apiClient";

// ============== TYPES ==============

export type User = {
  id: number;
  email: string;
  full_name: string;
  is_email_verified: boolean;
  is_platform_admin: boolean;
  created_at: string;
};

export type SignupResult = {
  user_id: number;
  pending_verification: boolean;
  verification_token?: string | null;
};

export type TokenResult = {
  access_token: string;
  token_type: string;
  user: User;
};

export type GoogleAuthResult = TokenResult & { created_new_user: boolean };

export type VerifyEmailResult = { verified: boolean; user_id: number };
export type ForgotPasswordResult = { sent: boolean; reset_token?: string | null };
export type ResetPasswordResult = { reset: boolean };

// ============== API CALLS ==============

export const authService = {
  signup: (email: string, password: string, full_name: string, trial: boolean = false) =>
    request<SignupResult>("/auth/signup", {
      method: "POST",
      noAuth: true,
      body: { email, password, full_name, trial },
    }),

  verifyEmail: (token: string) =>
    request<VerifyEmailResult>("/auth/verify-email", {
      method: "POST",
      noAuth: true,
      body: { token },
    }),

  login: (email: string, password: string) =>
    request<TokenResult>("/auth/login", {
      method: "POST",
      noAuth: true,
      body: { email, password },
    }),

  googleAuth: (google_id_token: string) =>
    request<GoogleAuthResult>("/auth/google", {
      method: "POST",
      noAuth: true,
      body: { google_id_token },
    }),

  forgotPassword: (email: string) =>
    request<ForgotPasswordResult>("/auth/forgot-password", {
      method: "POST",
      noAuth: true,
      body: { email },
    }),

  resetPassword: (token: string, new_password: string) =>
    request<ResetPasswordResult>("/auth/reset-password", {
      method: "POST",
      noAuth: true,
      body: { token, new_password },
    }),

  me: () => request<User>("/auth/me"),
};
