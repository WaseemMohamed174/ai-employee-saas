import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Sparkles,
  Zap,
  ShieldCheck,
  MessageSquareText,
  ArrowRight,
  LogOut,
  Check,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { useAuth } from "@/state/authStore";
import { planService, type Plan } from "@/services/planService";
import { healthService, type BackendHealth } from "@/services/healthService";
import { ApiError } from "@/services/apiClient";

// ============== HOME PAGE ==============

export default function Home() {
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const { user, logout } = useAuth();

  // ============== PLANS STATE ==============
  const [plans, setPlans] = useState<Plan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansError, setPlansError] = useState<string | null>(null);

  useEffect(() => {
    healthService.get().then(setHealth);
  }, []);

  useEffect(() => {
    let cancelled = false;
    planService
      .list()
      .then((result) => {
        if (cancelled) return;
        setPlans(result.plans);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setPlansError(err instanceof ApiError ? err.message : "Failed to load plans.");
      })
      .finally(() => {
        if (!cancelled) setPlansLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(theme);
  }, [theme]);

  return (
    <div className="min-h-dvh bg-background text-foreground">
      {/* ============== HEADER ============== */}
      <header className="border-b border-border/60 backdrop-blur-sm sticky top-0 z-10 bg-background/80">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-primary glow-primary rounded-md" />
            <span className="text-lg font-semibold tracking-tight">AI Employee</span>
            <span className="hidden text-xs text-muted-foreground sm:inline">v0.1.0</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className="rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
              aria-label="Toggle theme"
            >
              {theme === "dark" ? "Light" : "Dark"}
            </button>
            {user ? (
              <>
                <span className="hidden text-sm text-muted-foreground sm:inline" data-testid="user-email">
                  {user.email}
                </span>
                <button
                  type="button"
                  onClick={logout}
                  className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-surface"
                  aria-label="Log out"
                >
                  <LogOut className="h-4 w-4" /> Logout
                </button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="rounded-md border border-border px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-surface"
                >
                  Log in
                </Link>
                <Link
                  to="/signup"
                  className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
                >
                  Sign up
                </Link>
              </>
            )}
            <Link
              to="/api-docs"
              className="hidden rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground sm:inline-block"
            >
              API Docs
            </Link>
          </div>
        </div>
      </header>

      {/* ============== HERO ============== */}
      <main className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <section className="flex flex-col items-center gap-6 py-16 sm:py-24">
          <div
            data-testid="health-status"
            className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted-foreground"
          >
            <span
              className={`h-2 w-2 rounded-full ${health ? "bg-success" : "bg-warning"}`}
              aria-hidden="true"
            />
            {health ? `Backend: ${health.status}` : "Backend: starting…"}
          </div>

          <h1 className="max-w-3xl text-center text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
            AI assistant that knows your{" "}
            <span className="text-gradient-primary">store inside-out</span>.
          </h1>

          <p className="max-w-2xl text-center text-lg text-muted-foreground sm:text-xl">
            Rent an AI employee for your e-commerce chat. It replies from your own data, analyzes every
            conversation, and surfaces complaints, violations, and trends in one dashboard.
          </p>

          <div className="flex flex-col gap-3 sm:flex-row">
            <a
              href="/signup"
              className="inline-flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 glow-primary"
            >
              Get started free <ArrowRight className="h-4 w-4" />
            </a>
            <a
              href="/dashboard"
              className="inline-flex items-center gap-2 rounded-md border border-border px-5 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-surface"
            >
              View dashboard
            </a>
          </div>

          <p className="text-xs text-muted-foreground">
            Free trial: 5 requests / month, 1 API key. No card required.
          </p>
        </section>

        {/* ============== FEATURES ============== */}
        <section className="grid gap-4 pb-16 sm:grid-cols-2 lg:grid-cols-3">
          <FeatureCard
            icon={<MessageSquareText className="h-5 w-5 text-primary" />}
            title="RAG-powered chat"
            description="Keyword search over your store data, top 5 paragraphs always sent to the AI. No vector DB needed."
          />
          <FeatureCard
            icon={<Zap className="h-5 w-5 text-secondary" />}
            title="One unified API response"
            description="Reply + analysis + product ID + case status + transfer request — all in one call."
          />
          <FeatureCard
            icon={<ShieldCheck className="h-5 w-5 text-accent" />}
            title="Multi-tenant isolation"
            description="Each store gets its own SQLite file. Your data never touches another tenant."
          />
        </section>

        {/* ============== PLANS ============== */}
        <section className="pb-16" data-testid="plans-section">
          <div className="mb-8 text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Simple, transparent pricing</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Start free. Upgrade when your store grows. No pay-as-you-go surprises.
            </p>
          </div>

          {plansLoading && (
            <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground" data-testid="plans-loading">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading plans…
            </div>
          )}

          {plansError && !plansLoading && (
            <div
              className="mx-auto flex max-w-md items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
              data-testid="plans-error"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <span>{plansError}</span>
            </div>
          )}

          {!plansLoading && !plansError && plans.length === 0 && (
            <div className="py-12 text-center text-sm text-muted-foreground" data-testid="plans-empty">
              No plans available right now. Please check back later.
            </div>
          )}

          {!plansLoading && !plansError && plans.length > 0 && (
            <div
              className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
              data-testid="plans-grid"
            >
              {plans.map((plan) => (
                <PlanCard key={plan.code} plan={plan} highlighted={plan.code === "pro"} />
              ))}
            </div>
          )}

          <p className="mt-6 text-center text-xs text-muted-foreground">
            All plans include the full feature set. Differences are in data volume, tokens, and conversation limits.
          </p>
        </section>

        {/* ============== FOOTER ============== */}
        <footer className="border-t border-border py-8 text-center text-xs text-muted-foreground">
          AI Employee &middot; shop-assistant &middot; built with FastAPI + React + Tailwind v4
        </footer>
      </main>
    </div>
  );
}

// ============== FEATURE CARD COMPONENT ==============

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-5 shadow-sm transition-colors hover:border-primary/40">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-md bg-surface-2">{icon}</div>
      <h3 className="mb-1 text-base font-semibold">{title}</h3>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

// ============== PLAN CARD COMPONENT ==============

function PlanCard({ plan, highlighted }: { plan: Plan; highlighted: boolean }) {
  const features = [
    `${formatDataLimit(plan.data_limit_kb)} data storage`,
    `${formatNumber(plan.token_limit_month)} tokens / month`,
    `${formatNumber(plan.conversation_limit_month)} conversations / month`,
    plan.is_trial ? "1 API key, 5 requests total" : "Multiple API keys",
    "Full dashboard access",
  ];

  return (
    <div
      data-testid={`plan-card-${plan.code}`}
      className={`relative flex flex-col rounded-lg border p-5 shadow-sm transition-colors ${
        highlighted
          ? "border-primary glow-primary bg-surface"
          : "border-border bg-surface hover:border-primary/40"
      }`}
    >
      {highlighted && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-1 text-xs font-medium text-primary-foreground">
          Most popular
        </div>
      )}
      <h3 className="text-lg font-semibold">{plan.name}</h3>
      <div className="mt-2 mb-4">
        <span className="text-3xl font-bold tracking-tight">{plan.price_usd_display}</span>
      </div>
      <ul className="mb-5 space-y-2 text-sm text-muted-foreground">
        {features.map((feat) => (
          <li key={feat} className="flex items-start gap-2">
            <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-success" />
            <span>{feat}</span>
          </li>
        ))}
      </ul>
      <Link
        to="/signup"
        className={`mt-auto inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-opacity hover:opacity-90 ${
          highlighted
            ? "bg-primary text-primary-foreground"
            : "border border-border text-foreground hover:bg-surface-2"
        }`}
        data-testid={`plan-cta-${plan.code}`}
      >
        {plan.is_trial ? "Start free" : `Choose ${plan.name}`} <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}

// ============== FORMAT HELPERS ==============

function formatDataLimit(kb: number): string {
  if (kb < 1024) return `${kb} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb % 1 === 0 ? mb : mb.toFixed(0)} MB`;
  return `${(mb / 1024).toFixed(0)} GB`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n % 1_000_000 === 0 ? 0 : 1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n % 1_000 === 0 ? 0 : 1)}K`;
  return `${n}`;
}
