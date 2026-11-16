import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Sparkles,
  LayoutDashboard,
  MessageSquare,
  AlertCircle,
  ShieldAlert,
  Users,
  Bell,
  Database as DatabaseIcon,
  UserCircle,
  Activity,
  Code,
  CreditCard,
  KeyRound,
  LogOut,
  Menu,
  X,
  Loader2,
} from "lucide-react";
import { useAuth } from "@/state/authStore";

// ============== SIDEBAR ITEMS ==============

const SIDEBAR_ITEMS = [
  { to: "/dashboard", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/dashboard/conversations", label: "Conversations", icon: MessageSquare },
  { to: "/dashboard/complaints", label: "Complaints", icon: AlertCircle },
  { to: "/dashboard/violations", label: "Violations", icon: ShieldAlert },
  { to: "/dashboard/customers", label: "Customers", icon: Users },
  { to: "/dashboard/alerts", label: "Alerts", icon: Bell },
  { to: "/dashboard/database", label: "Database", icon: DatabaseIcon },
  { to: "/dashboard/persona", label: "Persona", icon: UserCircle },
  { to: "/dashboard/system-status", label: "System Status", icon: Activity },
  { to: "/dashboard/api-docs", label: "API Docs", icon: Code },
  { to: "/dashboard/plans", label: "Plans & Usage", icon: CreditCard },
  { to: "/dashboard/api-keys", label: "API Keys", icon: KeyRound },
];

// ============== DASHBOARD LAYOUT ==============

export default function DashboardLayout() {
  const { user, isLoading, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Redirect to /login if not authenticated.
  useEffect(() => {
    if (!isLoading && !user) {
      navigate("/login", { replace: true });
    }
  }, [isLoading, user, navigate]);

  if (isLoading) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!user) {
    return null; // useEffect will redirect
  }

  return (
    <div className="min-h-dvh bg-background text-foreground">
      {/* ============== SIDEBAR (desktop) ============== */}
      <aside
        className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-border bg-surface lg:block"
        data-testid="dashboard-sidebar"
      >
        <SidebarContent />
      </aside>

      {/* ============== SIDEBAR DRAWER (mobile) ============== */}
      {sidebarOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/50 lg:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
          <aside
            className="fixed inset-y-0 left-0 z-50 w-64 border-r border-border bg-surface lg:hidden"
            data-testid="dashboard-sidebar-mobile"
          >
            <div className="flex h-16 items-center justify-between border-b border-border px-4">
              <span className="text-sm font-semibold">Menu</span>
              <button
                type="button"
                onClick={() => setSidebarOpen(false)}
                className="rounded-md p-1.5 text-muted-foreground hover:text-foreground"
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <SidebarContent onNavigate={() => setSidebarOpen(false)} />
          </aside>
        </>
      )}

      {/* ============== MAIN CONTENT ============== */}
      <div className="lg:pl-60">
        {/* ============== TOPBAR ============== */}
        <header
          className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur-sm sm:px-6"
          data-testid="dashboard-topbar"
        >
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="rounded-md p-1.5 text-muted-foreground hover:text-foreground lg:hidden"
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <Link to="/dashboard" className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <span className="text-sm font-semibold tracking-tight">AI Employee</span>
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <span
              className="hidden items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground md:inline-flex"
              data-testid="live-refresh-badge"
              title="Every dashboard page re-fetches its data automatically while this tab is open"
            >
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
              Live · auto-refresh 5s
            </span>
            <span className="hidden text-sm text-muted-foreground sm:inline" data-testid="dashboard-user-email">
              {user.email}
            </span>
            <button
              type="button"
              onClick={() => {
                logout();
                navigate("/");
              }}
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
              aria-label="Log out"
            >
              <LogOut className="h-3.5 w-3.5" /> Logout
            </button>
          </div>
        </header>

        {/* ============== PAGE CONTENT ============== */}
        <main className="px-4 py-6 sm:px-6 lg:px-8" data-testid="dashboard-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

// ============== SIDEBAR CONTENT ==============

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex h-full flex-col">
      <div className="flex h-16 items-center gap-2 border-b border-border px-4">
        <Sparkles className="h-5 w-5 text-primary" />
        <span className="text-sm font-semibold tracking-tight">AI Employee</span>
      </div>
      <ul className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {SIDEBAR_ITEMS.map((item) => {
          const Icon = item.icon;
          const testId = `sidebar-link-${item.to.split("/").pop() || "dashboard"}`;
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-surface-2 hover:text-foreground"
                  }`
                }
                data-testid={testId}
              >
                <Icon className="h-4 w-4 flex-shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

// ============== COMING SOON PAGE ==============

export function ComingSoon({ title, featureId }: { title: string; featureId: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center" data-testid={`coming-soon-${featureId}`}>
      <div className="flex h-12 w-12 items-center justify-center rounded-md bg-surface-2">
        <Loader2 className="h-6 w-6 text-muted-foreground" />
      </div>
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="text-sm text-muted-foreground">
        This section will be built in <span className="font-mono text-foreground">{featureId}</span>.
      </p>
    </div>
  );
}

// ============== PROTECTED ROUTE WRAPPER ==============

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && !user) {
      navigate("/login", { replace: true });
    }
  }, [isLoading, user, navigate]);

  if (isLoading) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!user) return null;
  return <>{children}</>;
}
