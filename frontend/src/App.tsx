import { useCallback, useEffect, useState } from "react";
import {
  NavLink,
  Navigate,
  Outlet,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ApiError, api } from "./lib/api";
import DisruptionsPage from "./pages/Disruptions";
import FleetPage from "./pages/Fleet";
import HealthPage from "./pages/Health";
import LoginPage from "./pages/Login";
import OptimizationPage from "./pages/Optimization";
import OrdersPage from "./pages/Orders";
import OverviewPage from "./pages/Overview";
import TrackingPage from "./pages/Tracking";
import WarehousesPage from "./pages/Warehouses";

const NAV = [
  { to: "/overview", label: "Overview" },
  { to: "/orders", label: "Orders" },
  { to: "/warehouses", label: "Warehouses" },
  { to: "/fleet", label: "Fleet" },
  { to: "/optimization", label: "Optimization" },
  { to: "/tracking", label: "Live Tracking" },
  { to: "/disruptions", label: "Disruptions" },
  { to: "/health", label: "System Health" },
];

type ApiStatus = "checking" | "ok" | "degraded" | "down";

function StatusPill({ status, detail }: { status: ApiStatus; detail?: string }) {
  const tone =
    status === "ok"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
      : status === "degraded"
        ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
        : status === "down"
          ? "border-rose-500/40 bg-rose-500/10 text-rose-300"
          : "border-slate-600/40 bg-slate-700/20 text-slate-300";
  const text =
    status === "ok"
      ? "API healthy"
      : status === "degraded"
        ? "API degraded"
        : status === "down"
          ? "API unreachable"
          : "Checking API…";
  return (
    <span
      title={detail}
      className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1 text-xs font-medium ${tone}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {text}
    </span>
  );
}

function Layout() {
  const [status, setStatus] = useState<ApiStatus>("checking");
  const [detail, setDetail] = useState<string>();
  const [collapsed, setCollapsed] = useState(false);
  const [dark, setDark] = useState(true);

  const check = useCallback(async () => {
    setStatus("checking");
    try {
      const health = await api.health();
      const healthy = health.database === "connected" && health.redis === "connected";
      setStatus(healthy ? "ok" : "degraded");
      setDetail(
        `database: ${health.database}, redis: ${health.redis}`,
      );
    } catch (error) {
      setStatus("down");
      setDetail(error instanceof ApiError ? error.message : "Unexpected error");
    }
  }, []);

  useEffect(() => {
    void check();
    const timer = window.setInterval(() => void check(), 30_000);
    return () => window.clearInterval(timer);
  }, [check]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  return (
    <div className="flex h-full min-h-screen bg-slate-950">
      <aside
        className={`${collapsed ? "w-[68px]" : "w-60"} shrink-0 border-r border-panel-line bg-panel/80 transition-all`}
      >
        <div className="flex h-14 items-center gap-2.5 border-b border-panel-line px-4">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-indigo-600 text-xs font-bold text-white">
            RG
          </span>
          {!collapsed && (
            <span className="text-sm font-semibold tracking-tight text-slate-100">
              RouteGrid
            </span>
          )}
        </div>
        <nav className="flex flex-col gap-0.5 p-2">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              title={item.label}
              className={({ isActive }) =>
                `flex items-center gap-2.5 truncate rounded-lg px-3 py-2 text-sm transition ${
                  isActive
                    ? "bg-indigo-600/15 text-indigo-200"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                }`
              }
            >
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-70" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto p-3">
          <button className="btn w-full text-xs" onClick={() => setCollapsed((c) => !c)}>
            {collapsed ? "›" : "‹ Collapse"}
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-panel-line bg-panel/60 px-5">
          <p className="truncate text-sm font-medium text-slate-300">
            Logistics Operations Console
          </p>
          <div className="flex items-center gap-2">
            <StatusPill status={status} detail={detail} />
            <button
              className="btn text-xs"
              onClick={() => void check()}
              title="Re-check API health"
            >
              Refresh
            </button>
            <button className="btn text-xs" onClick={() => setDark((d) => !d)}>
              {dark ? "Light" : "Dark"}
            </button>
            <button
              className="btn text-xs"
              onClick={async () => {
                try {
                  await api.logout();
                } finally {
                  window.dispatchEvent(new Event("routegrid:unauthorized"));
                }
              }}
            >
              Sign out
            </button>
          </div>
        </header>

        <main className="min-w-0 flex-1 overflow-y-auto p-5">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState<"checking" | "in" | "out">("checking");

  useEffect(() => {
    api
      .me()
      .then(() => setSession("in"))
      .catch(() => setSession("out"));

    const onUnauthorized = () => setSession("out");
    window.addEventListener("routegrid:unauthorized", onUnauthorized);
    return () => window.removeEventListener("routegrid:unauthorized", onUnauthorized);
  }, []);

  if (session === "checking") {
    return (
      <div className="grid min-h-screen place-items-center text-sm text-slate-400">
        Checking session…
      </div>
    );
  }

  return (
    <Router>
      {session === "out" ? (
        <LoginPage onSignedIn={() => setSession("in")} />
      ) : (
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/overview" replace />} />
            <Route path="/overview" element={<OverviewPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/warehouses" element={<WarehousesPage />} />
            <Route path="/fleet" element={<FleetPage />} />
            <Route path="/optimization" element={<OptimizationPage />} />
            <Route path="/tracking" element={<TrackingPage />} />
            <Route path="/disruptions" element={<DisruptionsPage />} />
            <Route path="/health" element={<HealthPage />} />
            <Route path="*" element={<Navigate to="/overview" replace />} />
          </Route>
        </Routes>
      )}
    </Router>
  );
}
