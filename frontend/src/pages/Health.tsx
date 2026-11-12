import { Card, ErrorState, Loading, StatCard, StatusBadge, Table } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api } from "../lib/api";
import { dateTime, shortId } from "../lib/format";

export default function HealthPage() {
  const health = useAsync(() => api.health(), []);
  const routes = useAsync(() => api.routes(), []);

  const latest = (routes.data ?? [])[0] ?? null;

  return (
    <div className="space-y-5">
      <Card
        title="Service health"
        action={
          <button
            className="btn text-xs"
            onClick={() => {
              void health.reload();
              void routes.reload();
            }}
          >
            Re-check
          </button>
        }
      >
        {health.loading && <Loading label="Checking dependencies…" />}
        {health.error !== null && (
          <ErrorState error={health.error} onRetry={health.reload} />
        )}
        {health.data && (
          <>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <StatCard
                label="API"
                value="Online"
                tone="good"
                hint="This response came from the backend"
              />
              <StatCard
                label="PostgreSQL"
                value={health.data.database === "connected" ? "Connected" : "Unavailable"}
                tone={health.data.database === "connected" ? "good" : "bad"}
                hint="Source of truth for all operational state"
              />
              <StatCard
                label="Redis"
                value={health.data.redis === "connected" ? "Connected" : "Unavailable"}
                tone={health.data.redis === "connected" ? "good" : "warn"}
                hint="Position cache only — degraded, not fatal"
              />
              <StatCard
                label="Overall"
                value={health.data.status === "ok" ? "Healthy" : "Degraded"}
                tone={health.data.status === "ok" ? "good" : "warn"}
              />
            </div>
            {health.data.redis !== "connected" && (
              <p className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
                Redis is unavailable. Live position caching is bypassed; PostgreSQL remains
                the source of truth and the application continues to serve requests.
              </p>
            )}
          </>
        )}
      </Card>

      <Card title="GPS simulator & background work">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-panel-line p-4">
            <p className="label">Simulator</p>
            <p className="mt-1 text-sm text-slate-200">Available</p>
            <p className="mt-1 text-xs text-slate-500">
              In-process, deterministic, driven by the Advance endpoint. Not hardware GPS.
            </p>
          </div>
          <div className="rounded-lg border border-panel-line p-4">
            <p className="label">Background worker</p>
            <p className="mt-1 text-sm text-slate-200">Not deployed</p>
            <p className="mt-1 text-xs text-slate-500">
              Outbox rows are written transactionally but no poller consumes them yet.
            </p>
          </div>
          <div className="rounded-lg border border-panel-line p-4">
            <p className="label">Last optimization</p>
            <p className="mt-1 text-sm text-slate-200">
              {latest ? dateTime(latest.created_at) : "Never"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {latest ? `Route ${shortId(latest.id)} · ${latest.stops.length} stops` : "Run the optimizer to create the first batch."}
            </p>
          </div>
        </div>
      </Card>

      <Card title="Routes">
        {routes.loading && <Loading />}
        {routes.error !== null && <ErrorState error={routes.error} onRetry={routes.reload} />}
        {routes.data && routes.data.length === 0 && (
          <p className="py-6 text-center text-sm text-slate-500">No routes persisted yet.</p>
        )}
        {routes.data && routes.data.length > 0 && (
          <Table head={["Route", "Status", "Stops", "Created"]}>
            {routes.data.slice(0, 10).map((route) => (
              <tr key={route.id}>
                <td className="td font-mono text-xs">{shortId(route.id)}</td>
                <td className="td">
                  <StatusBadge status={route.status} />
                </td>
                <td className="td">{route.stops.length}</td>
                <td className="td">{dateTime(route.created_at)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
