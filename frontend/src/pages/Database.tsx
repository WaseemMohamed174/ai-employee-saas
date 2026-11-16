import { useEffect, useState, type FormEvent } from "react";
import { Database as DatabaseIcon, Upload, Loader2, AlertCircle, Check, ChevronLeft, ChevronRight, FileText } from "lucide-react";
import { ApiError } from "@/services/apiClient";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { dataService, type DataItem, type UploadLog } from "@/services/dataService";

// ============== DATABASE PAGE ==============

export default function DatabasePage() {
  const [items, setItems] = useState<DataItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Upload form state
  const [pasteContent, setPasteContent] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  // Logs state
  const [logs, setLogs] = useState<UploadLog[]>([]);

  useEffect(() => {
    fetchData(page);
  }, [page]);

  // S5: live refresh while the tab is visible — no spinner on poll ticks.
  useAutoRefresh(() => fetchData(page, false), 5000, [page]);

  async function fetchData(p: number, showSpinner: boolean = true) {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const [dataResult, logsResult] = await Promise.all([
        dataService.list(p, pageSize),
        dataService.listLogs(1, 5),
      ]);
      setItems(dataResult.items);
      setTotal(dataResult.total);
      setLogs(logsResult.logs);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load data.");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(e: FormEvent) {
    e.preventDefault();
    if (!pasteContent.trim()) return;
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);
    try {
      // Split by newlines — each non-empty line becomes an item.
      const lines = pasteContent.split("\n").filter((l) => l.trim());
      const items = lines.map((line, i) => ({ id: `line-${i + 1}`, content: line }));
      const result = await dataService.upload(items);
      setUploadSuccess(`Uploaded ${result.uploaded_count} items (${formatBytes(result.total_bytes)}).`);
      setPasteContent("");
      setPage(1);
      fetchData(1);
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Failed to upload data.");
    } finally {
      setUploading(false);
    }
  }

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-6" data-testid="database-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Database</h1>
        <p className="text-sm text-muted-foreground">
          Upload your store data (products, FAQs, policies). The AI will search through it to answer customer questions.
        </p>
      </div>

      {/* ============== UPLOAD FORM ============== */}
      <form
        onSubmit={handleUpload}
        className="rounded-lg border border-border bg-surface p-5"
        data-testid="upload-form"
      >
        <div className="mb-3 flex items-center gap-2">
          <Upload className="h-5 w-5 text-primary" />
          <h2 className="text-sm font-semibold">Upload data</h2>
        </div>
        <p className="mb-3 text-xs text-muted-foreground">
          Paste your data below — one item per line. Each line becomes a searchable item the AI can reference.
        </p>
        <textarea
          value={pasteContent}
          onChange={(e) => setPasteContent(e.target.value)}
          rows={6}
          placeholder={"Product ABC — $29.99 — Blue, size M\nReturn policy: 30 days, full refund\nFAQ: Do you ship internationally? Yes, we ship to 50+ countries."}
          data-testid="upload-textarea"
          className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
        />
        <div className="mt-3 flex items-center gap-3">
          <button
            type="submit"
            disabled={uploading || !pasteContent.trim()}
            data-testid="upload-submit"
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            {uploading ? "Uploading…" : "Upload"}
          </button>
          {uploadSuccess && (
            <span className="inline-flex items-center gap-1 text-sm text-success" data-testid="upload-success">
              <Check className="h-4 w-4" /> {uploadSuccess}
            </span>
          )}
          {uploadError && (
            <span className="inline-flex items-center gap-1 text-sm text-destructive" data-testid="upload-error">
              <AlertCircle className="h-4 w-4" /> {uploadError}
            </span>
          )}
        </div>
      </form>

      {/* ============== ERROR ============== */}
      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ============== DATA ITEMS ============== */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Stored data ({total} items)</h2>
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
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading data…
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface p-8 text-center" data-testid="data-empty">
            <DatabaseIcon className="mx-auto h-8 w-8 text-muted-foreground" />
            <h3 className="mt-2 text-sm font-semibold">No data yet</h3>
            <p className="mt-1 text-xs text-muted-foreground">Upload your first items using the form above.</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-border" data-testid="data-table">
            <table className="w-full text-sm">
              <thead className="bg-surface-2 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Item ID</th>
                  <th className="px-4 py-2 text-left font-medium">Content preview</th>
                  <th className="hidden px-4 py-2 text-left font-medium sm:table-cell">Source</th>
                  <th className="hidden px-4 py-2 text-left font-medium sm:table-cell">Uploaded</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((item) => (
                  <tr key={item.id} className="bg-surface/50">
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{item.item_id}</td>
                    <td className="px-4 py-3">{item.content_preview}</td>
                    <td className="hidden px-4 py-3 text-xs text-muted-foreground sm:table-cell">
                      <span className="rounded-full bg-surface-2 px-2 py-0.5">{item.source}</span>
                    </td>
                    <td className="hidden px-4 py-3 text-xs text-muted-foreground sm:table-cell">{formatDate(item.uploaded_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ============== UPLOAD LOGS ============== */}
      {logs.length > 0 && (
        <div>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <FileText className="h-4 w-4 text-muted-foreground" /> Recent uploads
          </h2>
          <div className="space-y-2" data-testid="upload-logs">
            {logs.map((log) => (
              <div key={log.id} className="flex items-center justify-between rounded-md border border-border bg-surface px-4 py-2 text-xs">
                <span className="text-muted-foreground">
                  {log.item_count} items · {formatBytes(log.file_size_bytes)} · via {log.source}
                </span>
                <span className="text-muted-foreground">{formatDate(log.uploaded_at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============== FORMAT HELPERS ==============

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}
