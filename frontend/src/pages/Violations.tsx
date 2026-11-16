import { useEffect, useState } from "react";
import { ShieldAlert, ShieldCheck, Loader2, AlertCircle, ChevronLeft, ChevronRight, Save } from "lucide-react";
import { ApiError } from "@/services/apiClient";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import {
  violationsService,
  type ViolationAction,
  type ViolationListItem,
  type ViolationPolicy,
} from "@/services/violationsService";

// ============== VIOLATIONS PAGE (F08) ==============

const ACTION_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All actions" },
  { value: "warning", label: "Warning" },
  { value: "temp_ban", label: "Temporary ban" },
  { value: "perma_ban", label: "Permanent ban" },
];

const POLICY_ACTIONS: ViolationAction[] = ["warning", "temp_ban", "perma_ban"];

export default function ViolationsPage() {
  const [items, setItems] = useState<ViolationListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [action, setAction] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [policies, setPolicies] = useState<ViolationPolicy[]>([]);
  const [policiesLoaded, setPoliciesLoaded] = useState(false);

  useEffect(() => {
    fetchViolations(page, action);
  }, [page, action]);

  // S5: live refresh while the tab is visible — no spinner on poll ticks.
  useAutoRefresh(() => fetchViolations(page, action, false), 5000, [page, action]);

  useEffect(() => {
    fetchPolicies();
  }, []);

  async function fetchViolations(p: number, a: string, showSpinner: boolean = true) {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const result = await violationsService.list(p, pageSize, a);
      setItems(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load violations.");
    } finally {
      setLoading(false);
    }
  }

  async function fetchPolicies() {
    try {
      const result = await violationsService.listPolicies();
      setPolicies(result.items);
    } catch {
      setPolicies([]);
    } finally {
      setPoliciesLoaded(true);
    }
  }

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-6" data-testid="violations-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Violations</h1>
          <p className="text-sm text-muted-foreground">
            Every action your AI employee took against abusive customers — and the policies that drive it.
          </p>
        </div>
        <select
          value={action}
          onChange={(e) => {
            setPage(1);
            setAction(e.target.value);
          }}
          data-testid="violations-filter"
          aria-label="Filter by action"
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
        >
          {ACTION_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* ============== POLICIES (FR-14) ============== */}
      <PolicyCard policies={policies} loaded={policiesLoaded} onSaved={fetchPolicies} />

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
            {action === "all" ? "All violations" : `${action} violations`} ({total})
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
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground" data-testid="violations-loading">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading violations…
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface p-8 text-center" data-testid="violations-empty">
            <ShieldAlert className="mx-auto h-8 w-8 text-muted-foreground" />
            <h3 className="mt-2 text-sm font-semibold">No violations recorded</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              {action === "all"
                ? "Actions against abusive customers will appear here as your AI employee detects them."
                : `No violations with the ${action} action. Try another filter.`}
            </p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border" data-testid="violations-table">
            <table className="w-full text-sm">
              <thead className="bg-surface-2 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Customer</th>
                  <th className="px-4 py-2 text-left font-medium">Action</th>
                  <th className="hidden px-4 py-2 text-left font-medium md:table-cell">Reason</th>
                  <th className="hidden px-4 py-2 text-left font-medium lg:table-cell">Recorded</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((violation) => (
                  <tr key={violation.id} className="bg-surface/50" data-testid="violation-row">
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs">{violation.customer_external_id}</span>
                    </td>
                    <td className="px-4 py-3">
                      <ActionBadge action={violation.action} />
                    </td>
                    <td className="hidden max-w-[360px] truncate px-4 py-3 text-muted-foreground md:table-cell">
                      {violation.reason ?? "—"}
                    </td>
                    <td className="hidden px-4 py-3 text-xs text-muted-foreground lg:table-cell">
                      {formatDate(violation.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-3 text-xs text-muted-foreground">
          Tip: a customer with a ban action can no longer chat — the AI ignores their messages.
        </p>
      </div>
    </div>
  );
}

// ============== POLICY CARD (FR-14) ==============

function PolicyCard({
  policies,
  loaded,
  onSaved,
}: {
  policies: ViolationPolicy[];
  loaded: boolean;
  onSaved: () => void | Promise<void>;
}) {
  const [action, setAction] = useState<ViolationAction>("warning");
  const [thresholdCount, setThresholdCount] = useState("2");
  const [windowHours, setWindowHours] = useState("24");
  const [autoApply, setAutoApply] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setFormError(null);
    setSavedNote(null);
    try {
      const count = Number(thresholdCount);
      const hours = Number(windowHours);
      if (!Number.isInteger(count) || count < 1 || !Number.isInteger(hours) || hours < 1) {
        throw new Error("Threshold and window must be whole numbers of at least 1.");
      }
      const result = await violationsService.savePolicy({
        action,
        threshold_count: count,
        threshold_window_hours: hours,
        auto_apply: autoApply,
      });
      // Refresh BEFORE the note: the success note must never show while the policy list
      // still shows the pre-save rows (the test counts rows right after the note).
      await onSaved();
      setSavedNote(`${result.policy.action} policy saved.`);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Could not save the policy.");
    } finally {
      setSaving(false);
    }
  }

  function editPolicy(policy: ViolationPolicy) {
    setAction(policy.action);
    setThresholdCount(String(policy.threshold_count));
    setWindowHours(String(policy.threshold_window_hours));
    setAutoApply(policy.auto_apply);
    setSavedNote(null);
    setFormError(null);
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4" data-testid="violations-policy-card">
      {/* Mobile (<sm): stack — icon+title on one row, description below full-width.
          A single flex row squeezed a 78-char description into 3 wrapped lines beside
          the title on 390px (observed in F08 mobile screenshots). */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <ShieldCheck className="h-4 w-4 shrink-0 text-primary" />
          Violation policies
        </h2>
        <span className="text-xs text-muted-foreground">
          when a customer collects N violations within the window, the action applies automatically
        </span>
      </div>

      {loaded && policies.length === 0 ? (
        <p className="mt-3 text-xs text-muted-foreground" data-testid="policies-empty">
          No policies yet — without one, the built-in defaults apply (high severity → permanent ban, else warning).
        </p>
      ) : (
        <ul className="mt-3 space-y-1.5" data-testid="policies-list">
          {policies.map((policy) => (
            <li
              key={policy.id}
              className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-xs"
              data-testid="policy-row"
            >
              <ActionBadge action={policy.action} />
              <span className="text-muted-foreground">
                {policy.threshold_count} violation(s) within {policy.threshold_window_hours}h
              </span>
              {policy.auto_apply ? (
                <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 font-medium text-emerald-500" data-testid="policy-auto">
                  auto-apply
                </span>
              ) : (
                <span className="rounded-full bg-surface-2 px-2 py-0.5 text-muted-foreground">manual</span>
              )}
              <button
                type="button"
                onClick={() => editPolicy(policy)}
                className="ml-auto text-xs text-primary hover:underline"
                data-testid="policy-edit"
              >
                Edit
              </button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={submit} className="mt-3 flex flex-wrap items-end gap-3" data-testid="policy-form">
        <label className="text-xs text-muted-foreground">
          Action
          <select
            value={action}
            onChange={(e) => setAction(e.target.value as ViolationAction)}
            data-testid="policy-action"
            aria-label="Policy action"
            className="mt-1 block rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          >
            {POLICY_ACTIONS.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </label>
        <label className="text-xs text-muted-foreground">
          Threshold (violations)
          <input
            type="number"
            min={1}
            max={100}
            value={thresholdCount}
            onChange={(e) => setThresholdCount(e.target.value)}
            data-testid="policy-threshold"
            aria-label="Violation threshold count"
            className="mt-1 block w-24 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          />
        </label>
        <label className="text-xs text-muted-foreground">
          Window (hours)
          <input
            type="number"
            min={1}
            max={720}
            value={windowHours}
            onChange={(e) => setWindowHours(e.target.value)}
            data-testid="policy-window"
            aria-label="Threshold window hours"
            className="mt-1 block w-24 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          />
        </label>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={autoApply}
            onChange={(e) => setAutoApply(e.target.checked)}
            data-testid="policy-auto-toggle"
            className="h-4 w-4"
          />
          Auto-apply
        </label>
        <button
          type="submit"
          disabled={saving}
          data-testid="policy-save"
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save policy
        </button>
      </form>

      {formError && (
        <p className="mt-2 text-xs text-destructive" data-testid="policy-error">{formError}</p>
      )}
      {savedNote && (
        <p className="mt-2 text-xs text-emerald-500" data-testid="policy-saved">{savedNote}</p>
      )}
    </div>
  );
}

// ============== ACTION BADGE ==============

function ActionBadge({ action }: { action: string | null }) {
  const styles: Record<string, string> = {
    warning: "bg-amber-500/10 text-amber-500",
    temp_ban: "bg-orange-500/10 text-orange-500",
    perma_ban: "bg-destructive/10 text-destructive",
  };
  const labels: Record<string, string> = {
    warning: "warning",
    temp_ban: "temp ban",
    perma_ban: "perma ban",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${styles[action ?? ""] ?? "bg-surface-2 text-muted-foreground"}`}
      data-testid="violation-action"
    >
      {labels[action ?? ""] ?? action ?? "unknown"}
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
