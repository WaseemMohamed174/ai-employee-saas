import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MessageSquare, Loader2, AlertCircle, ChevronLeft, ChevronRight } from "lucide-react";
import { ApiError } from "@/services/apiClient";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { conversationsService, type ConversationListItem } from "@/services/conversationsService";

// ============== CONVERSATIONS LIST PAGE ==============

const STATUS_OPTIONS = [
  { value: "all", label: "All statuses" },
  { value: "active", label: "Active" },
  { value: "transferred", label: "Transferred" },
];

export default function ConversationsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<ConversationListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchData(page, status);
  }, [page, status]);

  // S5: live refresh while the tab is visible — no spinner on poll ticks.
  useAutoRefresh(() => fetchData(page, status, false), 5000, [page, status]);

  async function fetchData(p: number, s: string, showSpinner: boolean = true) {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const result = await conversationsService.list(p, pageSize, s);
      setItems(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load conversations.");
    } finally {
      setLoading(false);
    }
  }

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-6" data-testid="conversations-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Conversations</h1>
          <p className="text-sm text-muted-foreground">
            Every customer chat handled by your AI employee — with its analysis and outcome.
          </p>
        </div>
        <select
          value={status}
          onChange={(e) => {
            setPage(1);
            setStatus(e.target.value);
          }}
          data-testid="conversations-filter"
          aria-label="Filter by status"
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
            {status === "all" ? "All conversations" : `${status} conversations`} ({total})
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
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground" data-testid="conversations-loading">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading conversations…
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface p-8 text-center" data-testid="conversations-empty">
            <MessageSquare className="mx-auto h-8 w-8 text-muted-foreground" />
            <h3 className="mt-2 text-sm font-semibold">No conversations yet</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              {status === "all"
                ? "Customer chats will appear here as soon as they message your store."
                : `No conversations with status "${status}". Try another filter.`}
            </p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border" data-testid="conversations-table">
            <table className="w-full text-sm">
              <thead className="bg-surface-2 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Customer</th>
                  <th className="px-4 py-2 text-left font-medium">Status</th>
                  <th className="hidden px-4 py-2 text-left font-medium sm:table-cell">Messages</th>
                  <th className="hidden px-4 py-2 text-left font-medium md:table-cell">Last message</th>
                  <th className="hidden px-4 py-2 text-left font-medium lg:table-cell">Last activity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((conv) => (
                  <tr
                    key={conv.id}
                    className="cursor-pointer bg-surface/50 transition-colors hover:bg-surface-2"
                    data-testid="conversation-row"
                    onClick={() => navigate(`/dashboard/conversations/${conv.id}`)}
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs">{conv.customer_external_id}</span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={conv.status} />
                    </td>
                    <td className="hidden px-4 py-3 text-muted-foreground sm:table-cell">{conv.messages_count}</td>
                    <td className="hidden max-w-[280px] truncate px-4 py-3 text-muted-foreground md:table-cell">
                      {conv.last_message_preview ?? "—"}
                    </td>
                    <td className="hidden px-4 py-3 text-xs text-muted-foreground lg:table-cell">
                      {formatDate(conv.last_message_at ?? conv.started_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-3 text-xs text-muted-foreground">
          Tip: click a row to open the full conversation with its analysis.{" "}
          <Link to="/dashboard/database" className="text-primary hover:underline">Upload data</Link>{" "}
          to improve AI answers.
        </p>
      </div>
    </div>
  );
}

// ============== STATUS BADGE ==============

export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: "bg-primary/10 text-primary",
    transferred: "bg-amber-500/10 text-amber-500",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${styles[status] ?? "bg-surface-2 text-muted-foreground"}`}
      data-testid="conversation-status"
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
