import { useEffect, useState } from "react";
import { Bell, Loader2, AlertCircle, ChevronLeft, ChevronRight, Check, BellOff } from "lucide-react";
import { ApiError } from "@/services/apiClient";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import {
  alertsService,
  type AlertListItem,
} from "@/services/alertsService";

// ============== ALERTS PAGE (F10) ==============

const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All types" },
  { value: "complaint_spike", label: "Complaint spike" },
  { value: "new_violation", label: "New violation" },
  { value: "token_near_limit", label: "Token near limit" },
  { value: "transfer_pending", label: "Transfer pending" },
];

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All states" },
  { value: "active", label: "Active" },
  { value: "dismissed", label: "Dismissed" },
];

export default function AlertsPage() {
  const [items, setItems] = useState<AlertListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [type, setType] = useState("all");
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isDesktop = useIsDesktop();
  // Dismiss flow state (per-row busy key + one shared note area).
  const [dismissingId, setDismissingId] = useState<number | null>(null);
  const [dismissNote, setDismissNote] = useState<{ id: number; ok: boolean; text: string } | null>(null);

  useEffect(() => {
    fetchAlerts(page, type, status);
  }, [page, type, status]);

  // S5: live refresh while the tab is visible — no spinner on poll ticks.
  useAutoRefresh(() => fetchAlerts(page, type, status, false), 5000, [page, type, status]);

  async function fetchAlerts(p: number, t: string, s: string, showSpinner: boolean = true) {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const result = await alertsService.list(p, pageSize, t, s);
      setItems(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load alerts.");
    } finally {
      if (showSpinner) setLoading(false);
    }
  }

  async function dismiss(alert: AlertListItem) {
    setDismissingId(alert.id);
    setDismissNote(null);
    try {
      const result = await alertsService.dismiss(alert.id);
      // Refresh BEFORE the note: the success note must never show while the table still
      // shows the alert as active (the test asserts the flipped state after the note).
      await fetchAlerts(page, type, status, false);
      setDismissNote({
        id: alert.id,
        ok: true,
        text: `Alert #${result.alert.id} (${result.alert.type}) dismissed.`,
      });
    } catch (err) {
      setDismissNote({
        id: alert.id,
        ok: false,
        text: err instanceof ApiError ? err.message : "Could not dismiss the alert.",
      });
    } finally {
      setDismissingId(null);
    }
  }

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-6" data-testid="alerts-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Alerts</h1>
          <p className="text-sm text-muted-foreground">
            What your AI employee wants you to know — complaint spikes, violations, token usage and pending human transfers.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={type}
            onChange={(e) => {
              setPage(1);
              setType(e.target.value);
            }}
            data-testid="alerts-type-filter"
            aria-label="Filter by alert type"
            className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          >
            {TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <select
            value={status}
            onChange={(e) => {
              setPage(1);
              setStatus(e.target.value);
            }}
            data-testid="alerts-status-filter"
            aria-label="Filter by alert state"
            className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* ============== ERROR ============== */}
      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ============== LIST ============== */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">
            {status === "active" ? "Active alerts" : status === "dismissed" ? "Dismissed alerts" : "All alerts"} ({total})
          </h2>
          {total > pageSize && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="rounded-md border border-border p-1.5 text-muted-foreground hover:text-foreground disabled:opacity-30"
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-xs text-muted-foreground">Page {page} of {totalPages}</span>
              <button
                type="button"
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="rounded-md border border-border p-1.5 text-muted-foreground hover:text-foreground disabled:opacity-30"
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>

        {loading ? (
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground" data-testid="alerts-loading">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading alerts…
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface p-8 text-center" data-testid="alerts-empty">
            <Bell className="mx-auto h-8 w-8 text-muted-foreground" />
            <h3 className="mt-2 text-sm font-semibold">No alerts here</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              {status === "active"
                ? "Nothing needs your attention — alerts appear when your store needs you."
                : status === "dismissed"
                  ? "No dismissed alerts yet — alerts you dismiss show up here."
                  : type === "all"
                    ? "Alerts appear here as your AI employee spots complaint spikes, violations, token usage or pending transfers."
                    : `No ${type} alerts. Try another type filter.`}
            </p>
          </div>
        ) : (
          <div data-testid="alerts-table">
            {isDesktop ? (
              <div className="overflow-hidden rounded-lg border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-surface-2 text-xs text-muted-foreground">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium">Alert</th>
                      <th className="px-4 py-2 text-left font-medium">Type</th>
                      <th className="hidden px-4 py-2 text-left font-medium md:table-cell">Severity</th>
                      <th className="hidden px-4 py-2 text-left font-medium lg:table-cell">Raised</th>
                      <th className="px-4 py-2 text-left font-medium">State</th>
                      <th className="px-4 py-2 text-right font-medium">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {items.map((alert) => (
                      <tr key={alert.id} className="bg-surface/50" data-testid="alert-row">
                        <td className="max-w-md px-4 py-3">
                          <span className="text-foreground/90">{alert.message}</span>
                        </td>
                        <td className="px-4 py-3">
                          <TypeBadge type={alert.type} />
                        </td>
                        <td className="hidden px-4 py-3 md:table-cell">
                          <SeverityBadge severity={alert.severity} />
                        </td>
                        <td className="hidden px-4 py-3 text-xs text-muted-foreground lg:table-cell">
                          {formatDate(alert.created_at)}
                        </td>
                        <td className="px-4 py-3">
                          <StateBadge dismissed={alert.dismissed_at !== null} dismissedAt={alert.dismissed_at} />
                        </td>
                        <td className="px-4 py-3 text-right">
                          {alert.dismissed_at === null ? (
                            <button
                              type="button"
                              onClick={() => dismiss(alert)}
                              disabled={dismissingId === alert.id}
                              data-testid="alert-dismiss"
                              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                            >
                              {dismissingId === alert.id
                                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                : <Check className="h-3.5 w-3.5" />}
                              Dismiss
                            </button>
                          ) : (
                            <BellOff className="ml-auto h-3.5 w-3.5 text-muted-foreground/30" />
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              /* Mobile (<md): stacked alert cards — the 5-column table cannot fit 390px
                 and clipping its overflow used to cut the Dismiss button in half. */
              <div className="divide-y divide-border overflow-hidden rounded-lg border border-border">
                {items.map((alert) => (
                  <div key={alert.id} className="bg-surface/50 p-3" data-testid="alert-row">
                    <p className="text-sm text-foreground/90">{alert.message}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <TypeBadge type={alert.type} />
                      <SeverityBadge severity={alert.severity} />
                      <StateBadge dismissed={alert.dismissed_at !== null} dismissedAt={alert.dismissed_at} />
                      {alert.dismissed_at === null ? (
                        <button
                          type="button"
                          onClick={() => dismiss(alert)}
                          disabled={dismissingId === alert.id}
                          data-testid="alert-dismiss"
                          className="ml-auto inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                        >
                          {dismissingId === alert.id
                            ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            : <Check className="h-3.5 w-3.5" />}
                          Dismiss
                        </button>
                      ) : (
                        <BellOff className="ml-auto h-3.5 w-3.5 text-muted-foreground/30" />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ============== DISMISS NOTE ============== */}
        {dismissNote && (
          <p
            className={`mt-3 text-xs ${dismissNote.ok ? "text-emerald-500" : "text-destructive"}`}
            data-testid={dismissNote.ok ? "dismiss-success" : "dismiss-error"}
          >
            {dismissNote.text}
          </p>
        )}

        <p className="mt-3 text-xs text-muted-foreground">
          Tip: complaint spikes are computed automatically when you open this page (complaint ratio of the recent chats) — dismissing an alert only marks it handled; the record stays for your audit trail.
        </p>
      </div>
    </div>
  );
}

// ============== RESPONSIVE VARIANT HOOK ==============

function useIsDesktop() {
  // One variant in the DOM (cards < 768px, table ≥ 768px) — CSS-hiding a second
  // variant would double every data-testid count in the Playwright suite.
  const [isDesktop, setIsDesktop] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(min-width: 768px)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const onChange = (event: MediaQueryListEvent) => setIsDesktop(event.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return isDesktop;
}

// ============== BADGES ==============

function TypeBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    complaint_spike: "bg-amber-500/10 text-amber-500",
    new_violation: "bg-destructive/10 text-destructive",
    token_near_limit: "bg-violet-500/10 text-violet-400",
    transfer_pending: "bg-sky-500/10 text-sky-400",
  };
  const labels: Record<string, string> = {
    complaint_spike: "complaint spike",
    new_violation: "new violation",
    token_near_limit: "token near limit",
    transfer_pending: "transfer pending",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${styles[type] ?? "bg-surface-2 text-muted-foreground"}`}
      data-testid="alert-type"
    >
      {labels[type] ?? type}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    info: "bg-sky-500/10 text-sky-400",
    warning: "bg-amber-500/10 text-amber-500",
    critical: "bg-destructive/10 text-destructive",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${styles[severity] ?? "bg-surface-2 text-muted-foreground"}`}
      data-testid="alert-severity"
    >
      {severity}
    </span>
  );
}

function StateBadge({ dismissed, dismissedAt }: { dismissed: boolean; dismissedAt: string | null }) {
  if (!dismissed) {
    return (
      <span
        className="inline-flex rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-500"
        data-testid="alert-state"
      >
        active
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 text-xs font-medium text-muted-foreground"
      data-testid="alert-state"
      title={dismissedAt ? `Dismissed ${formatDate(dismissedAt)}` : undefined}
    >
      dismissed
    </span>
  );
}

// ============== FORMAT HELPERS ==============

function formatDate(iso: string): string {
  try {
    const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}
