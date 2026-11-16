import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { MailCheck, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { authService } from "@/services/authService";
import { ApiError } from "@/services/apiClient";

// ============== VERIFY EMAIL PAGE ==============

type State = "idle" | "verifying" | "success" | "error" | "pending";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<State>(token ? "verifying" : "pending");
  const [errorMsg, setErrorMsg] = useState<string>("");

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    authService
      .verifyEmail(token)
      .then(() => {
        if (!cancelled) setState("success");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState("error");
        setErrorMsg(err instanceof ApiError ? err.message : "Verification failed.");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (state === "verifying") {
    return (
      <CenteredCard>
        <Loader2 className="mx-auto h-10 w-10 animate-spin text-primary" />
        <h1 className="mt-4 text-xl font-bold tracking-tight">Verifying your email…</h1>
        <p className="text-sm text-muted-foreground">Please wait a moment.</p>
      </CenteredCard>
    );
  }

  if (state === "success") {
    return (
      <CenteredCard>
        <CheckCircle2 className="mx-auto h-12 w-12 text-success" />
        <h1 className="mt-4 text-2xl font-bold tracking-tight">Email verified!</h1>
        <p className="text-sm text-muted-foreground">You can now log in to your account.</p>
        <Link
          to="/login"
          className="mt-4 inline-block rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          Go to login
        </Link>
      </CenteredCard>
    );
  }

  if (state === "error") {
    return (
      <CenteredCard>
        <AlertCircle className="mx-auto h-12 w-12 text-destructive" />
        <h1 className="mt-4 text-2xl font-bold tracking-tight">Verification failed</h1>
        <p className="text-sm text-muted-foreground">
          {errorMsg || "The verification link is invalid or expired."}
        </p>
        <Link
          to="/signup"
          className="mt-4 inline-block rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          Back to signup
        </Link>
      </CenteredCard>
    );
  }

  // pending: no token in URL — show the "check your email" state.
  return (
    <CenteredCard>
      <MailCheck className="mx-auto h-12 w-12 text-primary" />
      <h1 className="mt-4 text-2xl font-bold tracking-tight">Check your email</h1>
      <p className="text-sm text-muted-foreground">
        We sent a verification link to your email. Click it to activate your account.
      </p>
      <p className="mt-4 text-xs text-muted-foreground">
        In mock mode (no SMTP configured), the verification token is returned in the API response
        to the signup call. Use it like:{" "}
        <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono">
          /verify-email?token=YOUR_TOKEN
        </code>
      </p>
      <Link
        to="/login"
        className="mt-4 inline-block text-sm font-medium text-primary hover:opacity-80"
      >
        Already verified? Log in →
      </Link>
    </CenteredCard>
  );
}

// ============== CENTERED CARD LAYOUT ==============

function CenteredCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-md space-y-3 text-center">{children}</div>
    </div>
  );
}
