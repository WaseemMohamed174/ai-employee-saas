import { useEffect, useState } from "react";
import {
  AlertCircle,
  BadgeCheck,
  Check,
  CreditCard,
  Database,
  Loader2,
  MessageSquare,
  Sparkles,
  Zap,
} from "lucide-react";
import { ApiError } from "@/services/apiClient";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import {
  plansService,
  type PlanCatalogItem,
  type PlansOverview,
} from "@/services/plansService";

// ============== PLANS & USAGE PAGE (F14, FR-03 + FR-13) ==============
// Current plan + the three usage meters (tokens / conversations / data) + the paid
// catalog with mock-checkout switching (immediate activation, PRD defers real Stripe
// to F-Payment — the note says so honestly).

function formatKb(kb: number): string {
  if (kb >= 1024) return `${(kb / 1024).toFixed(kb % 1024 === 0 ? 0 : 1)} MB`;
  return `${kb} KB`;
}

function formatPrice(cents: number): string {
  if (cents === 0) return "Free";
  return `$${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, "0")}/mo`;
}

const USAGE_METER_ICONS = { tokens: Sparkles, conversations: MessageSquare, data: Database } as const;

export default function PlansUsagePage() {
  const [overview, setOverview] = useState<PlansOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [switchingCode, setSwitchingCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    fetchOverview();
  }, []);

  // S5: live refresh while the tab is visible — no spinner on poll ticks.
  useAutoRefresh(() => fetchOverview(false), 5000);

  async function fetchOverview(showSpinner: boolean = true) {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const result = await plansService.getOverview();
      setOverview(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load your plans and usage.");
    } finally {
      setLoading(false);
    }
  }

  async function upgrade(plan: PlanCatalogItem) {
    setSwitchingCode(plan.code);
    setError(null);
    setNote(null);
    try {
      const result = await plansService.changeSubscription(plan.code);
      // Mock checkout: the switch is already active server-side — refresh so the
      // meters and limits come from the same source of truth as every other page.
      const fresh = await plansService.getOverview();
      setOverview(fresh);
      setNote(
        `Checkout complete (mock mode) — your store is now on the ${result.subscription.plan.plan_name} plan. New limits apply immediately.`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The plan switch failed. Try again.");
    } finally {
      setSwitchingCode(null);
    }
  }

  return (
    <div className="space-y-6" data-testid="plans-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Plans &amp; Usage</h1>
        <p className="text-sm text-muted-foreground">
          Your current subscription, how much of it your AI employee has used this month, and the paid plans you can switch to — the switch activates immediately in mock-checkout mode.
        </p>
      </div>

      {/* ============== ERROR / NOTE ============== */}
      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive" data-testid="plans-error">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {note && (
        <div className="flex items-start gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-500" data-testid="plans-note">
          <Check className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{note}</span>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground" data-testid="plans-loading">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading your plan and usage…
        </div>
      ) : overview ? (
        <>
          {/* ============== CURRENT PLAN CARD ============== */}
          <div
            className="flex flex-col gap-2 rounded-lg border border-primary/40 bg-surface p-4 sm:flex-row sm:items-center sm:justify-between"
            data-testid="plans-current"
          >
            <span className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10">
                <BadgeCheck className="h-5 w-5 text-primary" />
              </span>
              <span>
                <span className="block text-sm font-semibold" data-testid="plans-current-name">
                  {overview.current.plan.plan_name}
                </span>
                <span className="block text-xs text-muted-foreground">
                  Current plan · since {overview.current.started_at.slice(0, 10)} · {formatPrice(overview.current.plan.price_usd_cents)}
                </span>
              </span>
            </span>
            <span
              className="inline-flex w-fit items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary"
              data-testid="plans-current-status"
            >
              {overview.current.status === "trial" ? "free trial" : overview.current.status}
            </span>
          </div>

          {/* ============== USAGE METERS ============== */}
          <div>
            <h2 className="mb-3 text-sm font-semibold">Usage this month</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3" data-testid="plans-usage">
              <UsageMeter
                kind="tokens"
                label="AI tokens"
                used={overview.usage.tokens_used}
                limit={overview.usage.plan.token_limit_month}
                format={(n) => n.toLocaleString("en-US")}
              />
              <UsageMeter
                kind="conversations"
                label="Conversations"
                used={overview.usage.conversations_used}
                limit={overview.usage.plan.conversation_limit_month}
                format={(n) => n.toLocaleString("en-US")}
              />
              <UsageMeter
                kind="data"
                label="Data uploaded"
                used={overview.usage.data_used_kb}
                limit={overview.usage.plan.data_limit_kb}
                format={formatKb}
              />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Meters reset monthly. Reaching a limit pauses the feature behind it (chat refuses with a clear upgrade message) — nothing is deleted.
            </p>
          </div>

          {/* ============== AVAILABLE PAID PLANS ============== */}
          <div>
            <h2 className="mb-3 text-sm font-semibold">Available plans</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="plans-available">
              {overview.available.map((plan) => (
                <PlanCard
                  key={plan.code}
                  plan={plan}
                  isCurrent={overview.current.plan.plan_code === plan.code}
                  switching={switchingCode === plan.code}
                  onUpgrade={() => upgrade(plan)}
                />
              ))}
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            Tip: checkout runs in mock mode for now (the switch activates immediately, no card charged) — the real Stripe integration lands in the payment phase with the same flow.
          </p>
        </>
      ) : null}
    </div>
  );
}

// ============== USAGE METER ==============

function UsageMeter({
  kind,
  label,
  used,
  limit,
  format,
}: {
  kind: keyof typeof USAGE_METER_ICONS;
  label: string;
  used: number;
  limit: number;
  format: (n: number) => string;
}) {
  const Icon = USAGE_METER_ICONS[kind];
  const percent = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const nearLimit = percent >= 90;
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4" data-testid={`usage-${kind}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Icon className="h-4 w-4 flex-shrink-0 text-primary" />
          {label}
        </span>
        <span
          className={`text-xs font-semibold ${nearLimit ? "text-warning" : "text-foreground"}`}
          data-testid={`usage-${kind}-value`}
        >
          {format(used)} / {format(limit)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-2" data-testid={`usage-${kind}-bar`}>
        <div
          className={`h-full rounded-full ${nearLimit ? "bg-warning" : "bg-primary"}`}
          style={{ width: `${percent}%` }}
          data-testid={`usage-${kind}-fill`}
        />
      </div>
      <span className="text-xs text-muted-foreground" data-testid={`usage-${kind}-percent`}>
        {percent}% used{nearLimit ? " — near the limit" : ""}
      </span>
    </div>
  );
}

// ============== PLAN CARD ==============

function PlanCard({
  plan,
  isCurrent,
  switching,
  onUpgrade,
}: {
  plan: PlanCatalogItem;
  isCurrent: boolean;
  switching: boolean;
  onUpgrade: () => void;
}) {
  const highlights: string[] = [
    `${plan.token_limit_month.toLocaleString("en-US")} AI tokens / month`,
    `${plan.conversation_limit_month.toLocaleString("en-US")} conversations / month`,
    `${formatKb(plan.data_limit_kb)} store data`,
  ];
  return (
    <div
      className={`flex flex-col gap-3 rounded-lg border p-4 ${
        isCurrent ? "border-primary/50 bg-primary/5" : "border-border bg-surface"
      }`}
      data-testid="plan-card"
      data-plan-code={plan.code}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-sm font-semibold" data-testid="plan-card-name">
          <Zap className={`h-4 w-4 flex-shrink-0 ${isCurrent ? "text-primary" : "text-muted-foreground"}`} />
          {plan.name}
        </span>
        <span className="text-sm font-bold" data-testid="plan-card-price">
          {plan.price_usd_display}
        </span>
      </div>
      <ul className="space-y-1">
        {highlights.map((line) => (
          <li key={line} className="flex items-start gap-1.5 text-xs text-muted-foreground">
            <Check className="mt-0.5 h-3 w-3 flex-shrink-0 text-emerald-500" />
            {line}
          </li>
        ))}
      </ul>
      {isCurrent ? (
        <span
          className="inline-flex w-fit items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary"
          data-testid="plan-card-current-badge"
        >
          <BadgeCheck className="h-3 w-3" /> Current plan
        </span>
      ) : (
        <button
          type="button"
          onClick={onUpgrade}
          disabled={switching}
          data-testid="plan-upgrade-btn"
          className="inline-flex w-fit items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-60"
        >
          {switching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CreditCard className="h-3.5 w-3.5" />}
          {switching ? "Processing…" : `Switch to ${plan.name}`}
        </button>
      )}
    </div>
  );
}
