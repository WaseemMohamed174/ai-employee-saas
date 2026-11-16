import { useEffect, useState } from "react";
import { Copy, Check, Plus, Trash2, AlertCircle, Loader2, KeyRound, Ban } from "lucide-react";
import { ApiError } from "@/services/apiClient";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { apiKeyService, type ApiKey } from "@/services/apiKeyService";

// ============== API KEYS PAGE ==============

export default function ApiKeys() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState("default");
  const [creating, setCreating] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [revokingId, setRevokingId] = useState<number | null>(null);

  useEffect(() => {
    fetchKeys();
  }, []);

  // S5: live refresh while the tab is visible — no spinner on poll ticks.
  useAutoRefresh(() => fetchKeys(false), 5000);

  async function fetchKeys(showSpinner: boolean = true) {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const result = await apiKeyService.list();
      setKeys(result.keys);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load API keys.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    setCreating(true);
    setCreateError(null);
    try {
      const result = await apiKeyService.create(newKeyName);
      setCreatedKey(result.key ?? null);
      setShowCreate(false);
      fetchKeys();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Failed to create API key.");
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(keyId: number) {
    if (!confirm("Are you sure? Revoked keys cannot be restored.")) return;
    setRevokingId(keyId);
    try {
      await apiKeyService.revoke(keyId);
      fetchKeys();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to revoke key.");
    } finally {
      setRevokingId(null);
    }
  }

  async function copyToClipboard(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback: select text
    }
  }

  // ============== CREATED KEY BANNER ==============

  if (createdKey) {
    return (
      <div className="space-y-6" data-testid="api-keys-created">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">API key created!</h1>
          <p className="text-sm text-muted-foreground">
            Copy this key now — you won't be able to see it again.
          </p>
        </div>
        <div className="rounded-lg border border-warning/40 bg-warning/10 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-warning">
            <AlertCircle className="h-4 w-4" /> Save this key securely
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded bg-background/50 px-3 py-2 font-mono text-xs">
              {createdKey}
            </code>
            <button
              type="button"
              onClick={() => copyToClipboard(createdKey)}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
              data-testid="copy-key"
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setCreatedKey(null)}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface"
        >
          Done
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="api-keys-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">API Keys</h1>
          <p className="text-sm text-muted-foreground">Create and revoke keys for your store widget.</p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          data-testid="create-key-btn"
        >
          <Plus className="h-4 w-4" /> New key
        </button>
      </div>

      {/* ============== CREATE FORM ============== */}
      {showCreate && (
        <div className="rounded-lg border border-border bg-surface p-4" data-testid="create-key-form">
          <h2 className="text-sm font-semibold">Create new API key</h2>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
            <div className="flex-1 space-y-1.5">
              <label htmlFor="key-name" className="block text-xs text-muted-foreground">Key name</label>
              <input
                id="key-name"
                type="text"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                maxLength={50}
                placeholder="e.g. production, staging"
                data-testid="key-name-input"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleCreate}
                disabled={creating}
                data-testid="key-submit"
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {creating ? "Creating…" : "Create"}
              </button>
              <button
                type="button"
                onClick={() => { setShowCreate(false); setCreateError(null); }}
                className="rounded-md border border-border px-4 py-2 text-sm hover:bg-surface"
              >
                Cancel
              </button>
            </div>
          </div>
          {createError && (
            <div className="mt-3 flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
              <span>{createError}</span>
            </div>
          )}
        </div>
      )}

      {/* ============== ERROR ============== */}
      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ============== LOADING ============== */}
      {loading && (
        <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading keys…
        </div>
      )}

      {/* ============== EMPTY ============== */}
      {!loading && !error && keys.length === 0 && (
        <div className="rounded-lg border border-border bg-surface p-8 text-center" data-testid="api-keys-empty">
          <KeyRound className="mx-auto h-8 w-8 text-muted-foreground" />
          <h2 className="mt-2 text-sm font-semibold">No API keys yet</h2>
          <p className="mt-1 text-xs text-muted-foreground">Create your first key to start using the chat API.</p>
        </div>
      )}

      {/* ============== TABLE ============== */}
      {!loading && !error && keys.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border" data-testid="api-keys-table">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 text-xs text-muted-foreground">
              <tr>
                {/* px-3 on <sm: 4 visible columns at 390px overflowed the card by ~7px
                    (scrolledWidth 363 vs 356) and overflow-hidden clipped the Actions edge. */}
                <th className="px-3 py-2 text-left font-medium sm:px-4">Name</th>
                <th className="px-3 py-2 text-left font-medium sm:px-4">Created</th>
                <th className="hidden px-3 py-2 text-left font-medium sm:table-cell sm:px-4">Last used</th>
                <th className="px-3 py-2 text-left font-medium sm:px-4">Status</th>
                <th className="px-3 py-2 text-right font-medium sm:px-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {keys.map((key) => (
                <tr key={key.id} className="bg-surface/50">
                  <td className="px-3 py-3 font-medium sm:px-4">{key.name}</td>
                  <td className="px-3 py-3 text-muted-foreground sm:px-4">{formatDate(key.created_at)}</td>
                  <td className="hidden px-3 py-3 text-muted-foreground sm:table-cell sm:px-4">
                    {key.last_used_at ? formatDate(key.last_used_at) : "—"}
                  </td>
                  <td className="px-3 py-3 sm:px-4">
                    {key.revoked_at ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-xs text-destructive">
                        <Ban className="h-3 w-3" /> Revoked
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-xs text-success">
                        <Check className="h-3 w-3" /> Active
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-right sm:px-4">
                    {!key.revoked_at && (
                      <button
                        type="button"
                        onClick={() => handleRevoke(key.id)}
                        disabled={revokingId === key.id}
                        className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:text-destructive disabled:opacity-50"
                        data-testid={`revoke-key-${key.id}`}
                      >
                        <Trash2 className="h-3 w-3" /> Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ============== FORMAT HELPER ==============

function formatDate(iso: string): string {
  try {
    const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}
