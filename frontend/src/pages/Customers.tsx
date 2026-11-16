import { useEffect, useState } from "react";
import { Users, Loader2, AlertCircle, ChevronLeft, ChevronRight, ShieldOff, ShieldX } from "lucide-react";
import { ApiError } from "@/services/apiClient";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import {
  customersService,
  type CustomerListItem,
} from "@/services/customersService";

// ============== CUSTOMERS PAGE (F09) ==============

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "active", label: "Active" },
  { value: "analyzing", label: "Analyzing" },
  { value: "warned", label: "Warned" },
  { value: "banned", label: "Banned" },
  { value: "transferred", label: "Transferred" },
];

export default function CustomersPage() {
  const [items, setItems] = useState<CustomerListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [caseStatus, setCaseStatus] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Unban flow state (per-row busy key + one shared note area).
  const [unbanningId, setUnbanningId] = useState<number | null>(null);
  const [unbanNote, setUnbanNote] = useState<{ id: number; ok: boolean; text: string } | null>(null);

  useEffect(() => {
    fetchCustomers(page, caseStatus);
  }, [page, caseStatus]);

  // S5: live refresh while the tab is visible — no spinner on poll ticks.
  useAutoRefresh(() => fetchCustomers(page, caseStatus, false), 5000, [page, caseStatus]);

  async function fetchCustomers(p: number, s: string, showSpinner: boolean = true) {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const result = await customersService.list(p, pageSize, s);
      setItems(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load customers.");
    } finally {
      if (showSpinner) setLoading(false);
    }
  }

  async function unban(customer: CustomerListItem) {
    setUnbanningId(customer.id);
    setUnbanNote(null);
    try {
      const result = await customersService.unban(customer.id);
      // Refresh BEFORE the note: the success note must never appear while the table
      // still shows the pre-action data (the test asserts on the refreshed rows).
      await fetchCustomers(page, caseStatus, false);
      setUnbanNote({
        id: customer.id,
        ok: true,
        text: `${result.customer.external_id} can chat again — ban lifted.`,
      });
    } catch (err) {
      setUnbanNote({
        id: customer.id,
        ok: false,
        text: err instanceof ApiError ? err.message : "Could not unban the customer.",
      });
    } finally {
      setUnbanningId(null);
    }
  }

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-6" data-testid="customers-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Customers</h1>
          <p className="text-sm text-muted-foreground">
            Everyone who ever chatted with your AI employee — their case status, and the bans you can lift.
          </p>
        </div>
        <select
          value={caseStatus}
          onChange={(e) => {
            setPage(1);
            setCaseStatus(e.target.value);
          }}
          data-testid="customers-filter"
          aria-label="Filter by case status"
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
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
            {caseStatus === "all" ? "All customers" : `${caseStatus} customers`} ({total})
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
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground" data-testid="customers-loading">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading customers…
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface p-8 text-center" data-testid="customers-empty">
            <Users className="mx-auto h-8 w-8 text-muted-foreground" />
            <h3 className="mt-2 text-sm font-semibold">No customers yet</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              {caseStatus === "all"
                ? "Customers appear here after their first chat with your AI employee."
                : `No customers with the ${caseStatus} status. Try another filter.`}
            </p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border" data-testid="customers-table">
            <table className="w-full text-sm">
              <thead className="bg-surface-2 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Customer</th>
                  <th className="px-4 py-2 text-left font-medium">Case status</th>
                  <th className="hidden px-4 py-2 text-left font-medium md:table-cell">Violations</th>
                  <th className="hidden px-4 py-2 text-left font-medium lg:table-cell">Banned</th>
                  <th className="hidden px-4 py-2 text-left font-medium lg:table-cell">First seen</th>
                  <th className="px-4 py-2 text-right font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((customer) => (
                  <tr key={customer.id} className="bg-surface/50" data-testid="customer-row">
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs">{customer.external_id}</span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={customer.case_status} />
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
                      {customer.violation_count}
                    </td>
                    <td className="hidden px-4 py-3 text-xs text-muted-foreground lg:table-cell">
                      {customer.banned_at
                        ? <span title={customer.banned_reason ?? undefined}>{formatDate(customer.banned_at)}</span>
                        : "—"}
                    </td>
                    <td className="hidden px-4 py-3 text-xs text-muted-foreground lg:table-cell">
                      {formatDate(customer.first_seen_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {customer.case_status === "banned" ? (
                        <button
                          type="button"
                          onClick={() => unban(customer)}
                          disabled={unbanningId === customer.id}
                          data-testid="customer-unban"
                          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                        >
                          {unbanningId === customer.id
                            ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            : <ShieldOff className="h-3.5 w-3.5" />}
                          Unban
                        </button>
                      ) : (
                        <ShieldX className="ml-auto h-3.5 w-3.5 text-muted-foreground/30" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ============== UNBAN NOTE ============== */}
        {unbanNote && (
          <p
            className={`mt-3 text-xs ${unbanNote.ok ? "text-emerald-500" : "text-destructive"}`}
            data-testid={unbanNote.ok ? "unban-success" : "unban-error"}
          >
            {unbanNote.text}
          </p>
        )}

        <p className="mt-3 text-xs text-muted-foreground">
          Tip: banned customers are ignored by the AI employee until you lift the ban — unbanning puts them back on active and keeps their violation history.
        </p>
      </div>
    </div>
  );
}

// ============== STATUS BADGE ==============

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: "bg-emerald-500/10 text-emerald-500",
    analyzing: "bg-sky-500/10 text-sky-400",
    warned: "bg-amber-500/10 text-amber-500",
    banned: "bg-destructive/10 text-destructive",
    transferred: "bg-violet-500/10 text-violet-400",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${styles[status] ?? "bg-surface-2 text-muted-foreground"}`}
      data-testid="customer-status"
    >
      {status}
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
