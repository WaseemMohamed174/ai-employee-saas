import { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Database,
  Loader2,
  Mail,
  Server,
  Sparkles,
} from "lucide-react";
import { ApiError } from "@/services/apiClient";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import {
  systemStatusService,
  formatUptime,
  type ServiceStatus,
  type SystemStatus,
} from "@/services/systemStatusService";

// ============== SYSTEM STATUS PAGE (F12, FR-13) ==============

const SERVICE_ICONS: Record<string, typeof Server> = {
  api: Server,
  database: Database,
  ai_provider: Sparkles,
  email: Mail,
};

export default function SystemStatusPage() {
  const [data, setData] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStatus();
  }, []);

  // S5: live refresh while the tab is visible — no spinner on poll ticks.
  useAutoRefresh(() => fetchStatus(false), 5000);

  async function fetchStatus(showSpinner: boolean = true) {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const result = await systemStatusService.get();
      setData(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load the system status.");
    } finally {
      setLoading(false);
    }
  }

  const allGood = data?.overall === "operational";

  return (
    <div className="space-y-6" data-testid="status-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">System Status</h1>
        <p className="text-sm text-muted-foreground">
          Live health of the platform services your AI employee runs on — measured from the running process every time you open this page.
        </p>
      </div>

      {/* ============== ERROR ============== */}
      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground" data-testid="status-loading">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading system status…
        </div>
      ) : data ? (
        <>
          {/* ============== OVERALL BANNER (stacks on mobile — F08 lesson) ============== */}
          <div
            className={`flex flex-col gap-2 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between ${
              allGood ? "border-emerald-500/40 bg-emerald-500/10" : "border-amber-500/40 bg-amber-500/10"
            }`}
            data-testid="status-overall"
          >
            <span className="flex items-center gap-2" data-testid="status-overall-text">
              {allGood ? (
                <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-emerald-500" />
              ) : (
                <AlertTriangle className="h-4 w-4 flex-shrink-0 text-amber-500" />
              )}
              <span className={`text-sm font-semibold ${allGood ? "text-emerald-500" : "text-amber-500"}`}>
                {allGood
                  ? "All systems operational"
                  : `${data.degraded_count} of ${data.services.length} services degraded`}
              </span>
            </span>
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span>v{data.version}</span>
              <span data-testid="status-uptime">API up {formatUptime(data.uptime_seconds)}</span>
            </span>
          </div>

          {/* ============== SERVICES GRID ============== */}
          <div>
            <h2 className="mb-3 text-sm font-semibold">Services ({data.services.length})</h2>
            <div
              className="grid grid-cols-1 gap-4 sm:grid-cols-2"
              data-testid="status-services"
            >
              {data.services.map((service) => (
                <ServiceCard key={service.id} service={service} />
              ))}
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            Tip: a degraded service is not an outage — the platform keeps answering in a safe fallback mode (for example the mock AI provider or mock email delivery). Configure the missing key in .env and reload this page to see it turn operational.
          </p>
        </>
      ) : null}
    </div>
  );
}

// ============== SERVICE CARD ==============

function ServiceCard({ service }: { service: ServiceStatus }) {
  const operational = service.status === "operational";
  const Icon = SERVICE_ICONS[service.id] ?? Activity;
  return (
    <div
      className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4"
      data-testid="status-service"
      data-service-id={service.id}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2" data-testid="status-service-name">
          <Icon className="h-4 w-4 flex-shrink-0 text-primary" />
          <span className="truncate text-sm font-semibold">{service.name}</span>
        </span>
        <span
          className={`inline-flex flex-shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
            operational ? "bg-emerald-500/10 text-emerald-500" : "bg-amber-500/10 text-amber-500"
          }`}
          data-testid="status-service-status"
          data-status={service.status}
        >
          {operational ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
          {service.status}
        </span>
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground" data-testid="status-service-detail">
        {service.detail}
      </p>
      {service.uptime_seconds !== null && (
        <p className="text-xs text-muted-foreground" data-testid="status-service-uptime">
          Uptime: {formatUptime(service.uptime_seconds)}
        </p>
      )}
    </div>
  );
}
