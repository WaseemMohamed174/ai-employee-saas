import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Sparkles, AlertCircle } from "lucide-react";
import { useAuth } from "@/state/authStore";
import { ApiError } from "@/services/apiClient";

// ============== SIGNUP PAGE ==============

export default function Signup() {
  const navigate = useNavigate();
  const { signup, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await signup(email, password, fullName);
      // After signup, the user needs to verify their email. Redirect to a generic verify-email page
      // that explains "check your email" (in mock mode the token is returned but the UI doesn't need it).
      navigate("/verify-email");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  // Support round S2: trial signup — the account is created pre-verified (no email
  // confirmation step) and the user lands straight on the dashboard to try the project.
  // The normal "Create account" flow above is untouched.
  async function handleTrial() {
    setLoading(true);
    setError(null);
    try {
      await signup(email, password, fullName, true);
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <div className="mb-3 inline-flex h-12 w-12 items-center justify-center rounded-md bg-primary/10 glow-primary">
            <Sparkles className="h-6 w-6 text-primary" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Create your account</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Start your 5-request free trial. No card required.
          </p>
        </div>

        <form
          data-testid="signup-form"
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border border-border bg-surface p-6 shadow-sm"
        >
          <Field
            id="signup-full-name"
            label="Full name (optional)"
            type="text"
            value={fullName}
            onChange={setFullName}
            autoComplete="name"
            data-testid="signup-full-name"
          />
          <Field
            id="signup-email"
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            autoComplete="email"
            required
            data-testid="signup-email"
          />
          <Field
            id="signup-password"
            label="Password (min 8 characters)"
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete="new-password"
            required
            minLength={8}
            data-testid="signup-password"
          />

          {error && (
            <div
              data-testid="signup-error"
              className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <button
              type="submit"
              disabled={loading}
              data-testid="signup-submit"
              className="w-full rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {loading ? "Creating account…" : "Create account"}
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={handleTrial}
              data-testid="trial-signup"
              className="w-full rounded-md border border-border bg-transparent px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground hover:border-foreground/40 disabled:opacity-50"
            >
              {loading ? "Preparing…" : "Sign up as trial"}
            </button>
          </div>
          <p className="text-center text-xs text-muted-foreground">
            "Sign up as trial" skips the email-confirmation step and opens the dashboard right away —
            meant for trying the project. Use "Create account" for a fully verified account.
          </p>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-primary hover:opacity-80">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}

// ============== FIELD COMPONENT ==============

function Field({
  id,
  label,
  type,
  value,
  onChange,
  autoComplete,
  required,
  minLength,
  "data-testid": testId,
}: {
  id: string;
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  required?: boolean;
  minLength?: number;
  "data-testid"?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        required={required}
        minLength={minLength}
        data-testid={testId}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
      />
    </div>
  );
}
