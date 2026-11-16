import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  Activity, AlertCircle, ArrowRight, BarChart3, Boxes, Clock3, CreditCard,
  Database, HardDrive, KeyRound, Loader2, MessageSquare, Sparkles, Store,
  UploadCloud,
} from "lucide-react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { ApiError } from "@/services/apiClient";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { storeService, type StoreWithSubscription } from "@/services/storeService";
import { overviewService, type OverviewData } from "@/services/overviewService";

// ============== DASHBOARD OVERVIEW PAGE (F15) ==============

export default function Dashboard() {
  const [storeData, setStoreData] = useState<StoreWithSubscription | null>(null);
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [noStore, setNoStore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    storeService
      .getMyStore()
      .then((result) => {
        if (cancelled) return;
        // The API returns `data: null` when the account has no store yet (it answers
        // 200 on purpose — a 404 probe here used to log console noise on every visit).
        if (result === null) setNoStore(true);
        else setStoreData(result);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setNoStore(true);
        } else {
          setError(err instanceof ApiError ? err.message : "Failed to load your store.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The overview needs a store (Owner JWT + store scope) — fetch it only once we have one.
  useEffect(() => {
    if (!storeData) return;
    let cancelled = false;
    overviewService
      .getOverview()
      .then((data) => {
        if (!cancelled) setOverview(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setOverviewError(err instanceof ApiError ? err.message : "Failed to load the overview.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [storeData]);

  // S5: live refresh of the overview while the tab is visible — silent on poll errors
  // (the initial load above already surfaces real failures).
  useAutoRefresh(() => {
    if (!storeData) return;
    overviewService
      .getOverview()
      .then((data) => setOverview(data))
      .catch(() => {});
  }, 5000, [storeData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground" data-testid="dashboard-loading">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading your dashboard…
      </div>
    );
  }

  if (noStore) {
    return <CreateStoreForm onCreated={(result) => { setStoreData(result); setNoStore(false); }} />;
  }

  if (error) {
    return (
      <div className="mx-auto flex max-w-md items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
        <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
        <span>{error}</span>
      </div>
    );
  }

  if (!storeData) return null;

  const { store, subscription, usage } = storeData;
  const tokensPct = usage.plan.token_limit_month > 0 ? (usage.tokens_used / usage.plan.token_limit_month) * 100 : 0;
  const convosPct = usage.plan.conversation_limit_month > 0 ? (usage.conversations_used / usage.plan.conversation_limit_month) * 100 : 0;
  const dataPct = usage.plan.data_limit_kb > 0 ? (usage.data_used_kb / usage.plan.data_limit_kb) * 100 : 0;

  const stats = overview?.stats ?? null;
  const uploadSeries = (overview?.uploads_per_day ?? []).map((p) => ({ ...p, label: p.day.slice(5) }));
  const sourceData = Object.entries(overview?.items_by_source ?? {})
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));
  const keysData = [
    { name: "active", count: overview?.keys_by_status.active ?? 0 },
    { name: "revoked", count: overview?.keys_by_status.revoked ?? 0 },
  ];

  return (
    <div className="space-y-6" data-testid="dashboard-overview">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Welcome to {store.name}</h1>
        <p className="text-sm text-muted-foreground">
          Plan: <span className="text-foreground">{subscription.plan.plan_name}</span> · Slug:{" "}
          <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs">{store.slug}</code>
        </p>
      </div>

      {/* ============== STORE ACTIVITY STATS (F15) ============== */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4" data-testid="overview-stats">
          <StatCard testId="overview-stat-items" icon={<Boxes className="h-4 w-4 text-primary" />} label="Items stored" value={stats.items_total} />
          <StatCard testId="overview-stat-bytes" icon={<HardDrive className="h-4 w-4 text-secondary" />} label="Data size" value={formatBytes(stats.bytes_total)} />
          <StatCard testId="overview-stat-uploads" icon={<UploadCloud className="h-4 w-4 text-accent" />} label="Uploads" value={stats.uploads_count} />
          <StatCard testId="overview-stat-keys" icon={<KeyRound className="h-4 w-4 text-success" />} label="Active API keys" value={stats.keys_active} />
          <StatCard testId="overview-stat-conversations" icon={<MessageSquare className="h-4 w-4 text-info" />} label="Conversations" value={stats.conversations_total} />
          <StatCard testId="overview-stat-complaints" icon={<AlertCircle className="h-4 w-4 text-warning" />} label="Complaints" value={stats.complaints_total} />
          <StatCard testId="overview-stat-alerts" icon={<Activity className="h-4 w-4 text-destructive" />} label="Active alerts" value={stats.alerts_active} />
          <StatCard testId="overview-stat-revoked" icon={<KeyRound className="h-4 w-4 text-muted-foreground" />} label="Revoked keys" value={stats.keys_revoked} />
        </div>
      )}

      {overviewError && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive" data-testid="overview-error">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{overviewError}</span>
        </div>
      )}

      {/* ============== CHARTS (F15) ============== */}
      {overview && (
        <div className="grid gap-4 lg:grid-cols-3" data-testid="overview-charts">
          <ChartCard title="Uploads — last 14 days" icon={<BarChart3 className="h-4 w-4 text-primary" />} testId="chart-uploads-area">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={uploadSeries} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="label" tick={{ fill: "var(--color-muted)", fontSize: 11 }} tickLine={false} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} tick={{ fill: "var(--color-muted)", fontSize: 11 }} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: "var(--color-surface-2)", border: "1px solid var(--color-border)", borderRadius: 12 }}
                  labelStyle={{ color: "var(--color-text)" }}
                  itemStyle={{ color: "var(--color-primary)" }}
                />
                <Area type="monotone" dataKey="items" name="items" stroke="var(--color-primary)" fill="var(--color-primary)" fillOpacity={0.18} strokeWidth={2} dot={{ r: 3, fill: "var(--color-primary)" }} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Items by source" icon={<Database className="h-4 w-4 text-secondary" />} testId="chart-source-donut">
            {sourceData.length === 0 ? (
              <EmptyChart text="No uploads yet — the donut fills up after your first upload." />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={sourceData} dataKey="value" nameKey="name" innerRadius={48} outerRadius={72} paddingAngle={3} strokeWidth={0} isAnimationActive={false}>
                    {sourceData.map((entry) => (
                      <Cell key={entry.name} fill={SOURCE_COLORS[entry.name] ?? "var(--color-accent)"} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "var(--color-surface-2)", border: "1px solid var(--color-border)", borderRadius: 12 }}
                    itemStyle={{ color: "var(--color-text)" }}
                  />
                  <Legend formatter={(value) => <span style={{ color: "var(--color-muted)" }}>{value}</span>} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard title="API keys by status" icon={<KeyRound className="h-4 w-4 text-success" />} testId="chart-keys-bar">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={keysData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: "var(--color-muted)", fontSize: 11 }} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: "var(--color-muted)", fontSize: 11 }} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: "var(--color-surface-2)", border: "1px solid var(--color-border)", borderRadius: 12 }}
                  labelStyle={{ color: "var(--color-text)" }}
                  itemStyle={{ color: "var(--color-success)" }}
                />
                <Bar dataKey="count" name="keys" radius={[6, 6, 0, 0]} barSize={44} isAnimationActive={false}>
                  <Cell fill="var(--color-success)" />
                  <Cell fill="var(--color-danger)" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      {/* ============== RECENT ACTIVITY (F15) ============== */}
      {overview && (
        <div className="rounded-lg border border-border bg-surface p-5" data-testid="recent-activity">
          <div className="flex items-center gap-2">
            <Clock3 className="h-5 w-5 text-primary" />
            <h2 className="text-base font-semibold">Recent activity</h2>
          </div>
          <div className="mt-4 grid gap-6 lg:grid-cols-3">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Latest uploads</h3>
              {overview.recent_uploads.length === 0 ? (
                <p className="mt-2 text-sm text-muted-foreground">No uploads yet.</p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {overview.recent_uploads.map((u) => (
                    <li key={u.id} data-testid="recent-upload-row" className="flex items-center justify-between rounded-md bg-surface-2 px-3 py-2 text-sm">
                      <span className="font-medium">{u.source}</span>
                      <span className="text-xs text-muted-foreground">
                        {u.item_count} items · {formatBytes(u.file_size_bytes)} · {u.uploaded_at.slice(0, 16)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Latest conversations</h3>
              {overview.recent_conversations.length === 0 ? (
                <p className="mt-2 text-sm text-muted-foreground" data-testid="recent-conversations-empty">
                  No conversations yet — they appear when customers start chatting with your AI.
                </p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {overview.recent_conversations.map((c) => (
                    <li key={c.id} data-testid="recent-conversation-row" className="flex items-center justify-between rounded-md bg-surface-2 px-3 py-2 text-sm">
                      <span className="font-medium">#{c.id}</span>
                      <span className="text-xs text-muted-foreground">{c.status} · {c.started_at.slice(0, 16)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Latest alerts</h3>
              {overview.recent_alerts.length === 0 ? (
                <p className="mt-2 text-sm text-muted-foreground" data-testid="recent-alerts-empty">No alerts yet.</p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {overview.recent_alerts.map((a) => (
                    <li key={a.id} data-testid="recent-alert-row" className="flex items-center justify-between rounded-md bg-surface-2 px-3 py-2 text-sm">
                      <span className="font-medium">{a.type}</span>
                      <span className="text-xs text-muted-foreground">{a.severity} · {a.created_at.slice(0, 16)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ============== USAGE STATS ============== */}
      <div className="grid gap-4 sm:grid-cols-3">
        <UsageCard
          label="Tokens used"
          value={`${usage.tokens_used.toLocaleString()} / ${usage.plan.token_limit_month.toLocaleString()}`}
          pct={tokensPct}
          data-testid="usage-tokens"
        />
        <UsageCard
          label="Conversations"
          value={`${usage.conversations_used} / ${usage.plan.conversation_limit_month}`}
          pct={convosPct}
          data-testid="usage-conversations"
        />
        <UsageCard
          label="Data stored"
          value={`${formatKb(usage.data_used_kb)} / ${formatKb(usage.plan.data_limit_kb)}`}
          pct={dataPct}
          data-testid="usage-data"
        />
      </div>

      {/* ============== QUICK ACTIONS ============== */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <QuickAction
          to="/dashboard/api-keys"
          icon={<KeyRound className="h-5 w-5 text-primary" />}
          title="Manage API keys"
          description="Create and revoke keys for your store widget."
        />
        <QuickAction
          to="/dashboard/database"
          icon={<Store className="h-5 w-5 text-secondary" />}
          title="Upload store data"
          description="Add products, FAQs, policies — anything the AI should know."
        />
        <QuickAction
          to="/dashboard/plans"
          icon={<CreditCard className="h-5 w-5 text-accent" />}
          title="Upgrade plan"
          description="Move beyond Free Trial for more tokens and conversations."
        />
      </div>

      <div className="rounded-lg border border-border bg-surface p-5">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <h2 className="text-base font-semibold">Next steps</h2>
        </div>
        <ol className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li>1. Create an API key (above) and copy it.</li>
          <li>2. Upload your store data (products, FAQs, policies).</li>
          <li>3. Integrate the chat endpoint in your store widget.</li>
        </ol>
        <Link
          to="/dashboard/api-docs"
          className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:opacity-80"
        >
          Read the API docs <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

// ============== CREATE STORE FORM ==============

function CreateStoreForm({ onCreated }: { onCreated: (result: StoreWithSubscription) => void }) {
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await storeService.createStore(slug, name);
      onCreated(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create store.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-6 py-8" data-testid="create-store-form">
      <div className="text-center">
        <div className="mb-3 inline-flex h-12 w-12 items-center justify-center rounded-md bg-primary/10">
          <Store className="h-6 w-6 text-primary" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight">Create your store</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Set up your store to start using the AI assistant. You'll get a Free Trial with 5 requests/month.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-border bg-surface p-6 shadow-sm">
        <div className="space-y-1.5">
          <label htmlFor="store-name" className="block text-sm font-medium">Store name</label>
          <input
            id="store-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={100}
            placeholder="My Awesome Store"
            data-testid="store-name-input"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="store-slug" className="block text-sm font-medium">
            Store slug <span className="text-muted-foreground">(lowercase, hyphens, 3-40 chars)</span>
          </label>
          <input
            id="store-slug"
            type="text"
            value={slug}
            onChange={(e) => setSlug(e.target.value.toLowerCase())}
            required
            minLength={3}
            maxLength={40}
            pattern="[a-z0-9][a-z0-9-]*[a-z0-9]"
            placeholder="my-awesome-store"
            data-testid="store-slug-input"
            className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          />
        </div>

        {error && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          data-testid="store-submit"
          className="w-full rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Creating store…" : "Create store"}
        </button>
      </form>
    </div>
  );
}

// ============== OVERVIEW PIECES (F15) ==============

const SOURCE_COLORS: Record<string, string> = {
  api: "var(--color-primary)",
  dashboard: "var(--color-secondary)",
};

function StatCard({ icon, label, value, testId }: { icon: React.ReactNode; label: string; value: number | string; testId: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4" data-testid={testId}>
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">{icon} {label}</div>
      <div className="mt-1 text-lg font-semibold" data-value>{value}</div>
    </div>
  );
}

function ChartCard({ title, icon, testId, children }: { title: string; icon: React.ReactNode; testId: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4" data-testid={testId}>
      <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">{icon} {title}</div>
      {children}
    </div>
  );
}

function EmptyChart({ text }: { text: string }) {
  return (
    <div className="flex h-[220px] items-center justify-center px-6 text-center text-sm text-muted-foreground" data-testid="chart-empty">
      {text}
    </div>
  );
}

// ============== USAGE CARD ==============

function UsageCard({ label, value, pct, ...rest }: { label: string; value: string; pct: number }) {
  const clampedPct = Math.min(pct, 100);
  return (
    <div className="rounded-lg border border-border bg-surface p-4" {...rest}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-2">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${clampedPct}%` }}
        />
      </div>
    </div>
  );
}

// ============== QUICK ACTION CARD ==============

function QuickAction({ to, icon, title, description }: { to: string; icon: React.ReactNode; title: string; description: string }) {
  return (
    <Link
      to={to}
      className="block rounded-lg border border-border bg-surface p-4 transition-colors hover:border-primary/40"
    >
      <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-md bg-surface-2">{icon}</div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-1 text-xs text-muted-foreground">{description}</p>
    </Link>
  );
}

// ============== FORMAT HELPERS ==============

function formatKb(kb: number): string {
  if (kb < 1024) return `${kb} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(0)} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}

/** Byte size the way the stat card and the tests read it: exact "N B" under 1 KB, then whole KB. */
function formatBytes(numBytes: number): string {
  if (numBytes < 1024) return `${numBytes} B`;
  return `${Math.floor(numBytes / 1024)} KB`;
}
