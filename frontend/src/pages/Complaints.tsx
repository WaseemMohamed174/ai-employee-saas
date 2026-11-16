import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ThumbsDown, Loader2, AlertCircle, ChevronLeft, ChevronRight } from "lucide-react";
import { ApiError } from "@/services/apiClient";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { complaintsService, type ComplaintListItem } from "@/services/complaintsService";

// ============== COMPLAINTS LIST PAGE (F07) ==============

const SENTIMENT_OPTIONS = [
  { value: "all", label: "All sentiments" },
  { value: "negative", label: "Negative" },
  { value: "neutral", label: "Neutral" },
  { value: "positive", label: "Positive" },
];

export default function ComplaintsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<ComplaintListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [sentiment, setSentiment] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchData(page, sentiment);
  }, [page, sentiment]);

  // S5: live refresh while the tab is visible — no spinner on poll ticks.
  useAutoRefresh(() => fetchData(page, sentiment, false), 5000, [page, sentiment]);

  async function fetchData(p: number, s: string, showSpinner: boolean = true) {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const result = await complaintsService.list(p, pageSize, s);
      setItems(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load complaints.");
    } finally {
      setLoading(false);
    }
  }

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-6" data-testid="complaints-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Complaints</h1>
          <p className="text-sm text-muted-foreground">
            Every message your AI employee flagged as a complaint — click one to see the full conversation.
          </p>
        </div>
        <select
          value={sentiment}
          onChange={(e) => {
            setPage(1);
            setSentiment(e.target.value);
          }}
          data-testid="complaints-filter"
          aria-label="Filter by sentiment"
          className="rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
        >
          {SENTIMENT_OPTIONS.map((opt) => (
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
            {sentiment === "all" ? "All complaints" : `${sentiment} complaints`} ({total})
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
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground" data-testid="complaints-loading">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading complaints…
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface p-8 text-center" data-testid="complaints-empty">
            <ThumbsDown className="mx-auto h-8 w-8 text-muted-foreground" />
            <h3 className="mt-2 text-sm font-semibold">No complaints yet</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              {sentiment === "all"
                ? "Flagged customer complaints will appear here as your AI employee detects them."
                : `No complaints with ${sentiment} sentiment. Try another filter.`}
            </p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border" data-testid="complaints-table">
            <table className="w-full text-sm">
              <thead className="bg-surface-2 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Customer</th>
                  <th className="px-4 py-2 text-left font-medium">Sentiment</th>
                  <th className="hidden px-4 py-2 text-left font-medium md:table-cell">Message</th>
                  <th className="hidden px-4 py-2 text-left font-medium lg:table-cell">Received</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((complaint) => (
                  <tr
                    key={complaint.analysis_id}
                    className="cursor-pointer bg-surface/50 transition-colors hover:bg-surface-2"
                    data-testid="complaint-row"
                    onClick={() => navigate(`/dashboard/conversations/${complaint.conversation_id}`)}
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs">{complaint.customer_external_id}</span>
                    </td>
                    <td className="px-4 py-3">
                      <SentimentBadge sentiment={complaint.sentiment} />
                      {complaint.severity && (
                        <span
                          className="ml-2 inline-flex rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive"
                          data-testid="complaint-severity"
                        >
                          {complaint.severity}
                        </span>
                      )}
                    </td>
                    <td className="hidden max-w-[360px] truncate px-4 py-3 text-muted-foreground md:table-cell">
                      {complaint.customer_message ?? complaint.message_excerpt}
                    </td>
                    <td className="hidden px-4 py-3 text-xs text-muted-foreground lg:table-cell">
                      {formatDate(complaint.sent_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-3 text-xs text-muted-foreground">
          Tip: click a row to open the full conversation behind the complaint.
        </p>
      </div>
    </div>
  );
}

// ============== SENTIMENT BADGE ==============

function SentimentBadge({ sentiment }: { sentiment: string | null }) {
  const styles: Record<string, string> = {
    negative: "bg-destructive/10 text-destructive",
    neutral: "bg-surface-2 text-muted-foreground",
    positive: "bg-emerald-500/10 text-emerald-500",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${styles[sentiment ?? ""] ?? "bg-surface-2 text-muted-foreground"}`}
      data-testid="complaint-sentiment"
    >
      {sentiment ?? "unknown"}
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
