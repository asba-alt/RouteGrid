import { useState } from "react";
import {
  Card,
  EmptyState,
  ErrorState,
  Loading,
  StatCard,
  StatusBadge,
  Table,
} from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api, type BatchSolveResult } from "../lib/api";
import { dateTime, km, minutes, shortId } from "../lib/format";

export default function OptimizationPage() {
  const [result, setResult] = useState<BatchSolveResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [useLocalSearch, setUseLocalSearch] = useState(false);

  const routes = useAsync(() => api.routes(), []);

  async function run() {
    if (running) return; // prevent duplicate batch solves
    setRunning(true);
    setError(null);
    try {
      const outcome = await api.optimize({ use_local_search: useLocalSearch });
      setResult(outcome);
      await routes.reload();
    } catch (err) {
      setError(err);
    } finally {
      setRunning(false);
    }
  }

  const routeRows = routes.data ?? [];

  return (
    <div className="space-y-5">
      <Card
        title="Batch optimization"
        action={
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <input
                type="checkbox"
                checked={useLocalSearch}
                onChange={(e) => setUseLocalSearch(e.target.checked)}
              />
              Use local search
            </label>
            <button className="btn btn-primary text-xs" onClick={() => void run()} disabled={running}>
              {running ? "Solving…" : "Run optimization"}
            </button>
          </div>
        }
      >
        <p className="text-sm text-slate-400">
          Assigns every order awaiting allocation to operational vehicles and sequences
          their stops together (CVRP, weight capacity as a hard constraint). Deliveries
          that cannot be legally served are reported as unassigned rather than
          overloaded.
        </p>
        {error !== null && <div className="mt-3"><ErrorState error={error} /></div>}

        {result && (
          <>
            <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
              <StatCard label="Routes created" value={result.routes.length} />
              <StatCard
                label="Unassigned"
                value={result.unassigned_fulfillment_group_ids.length}
                tone={result.unassigned_fulfillment_group_ids.length ? "warn" : "good"}
              />
              <StatCard label="Total distance" value={km(result.total_distance_m)} />
              <StatCard label="Estimated drive time" value={minutes(result.total_travel_time_seconds)} />
            </div>
            <p className="mt-3 text-xs text-slate-500">
              {result.eligible_order_count} eligible order(s) ·{" "}
              {result.operational_vehicle_count} operational vehicle(s) ·{" "}
              {result.skipped_orders_without_location} skipped (no delivery location) ·{" "}
              solver {result.solved ? "found a solution" : "did not find a solution"}
            </p>
          </>
        )}
      </Card>

      {result && (
        <Card title="Assignments from this run">
          {result.routes.length === 0 ? (
            <EmptyState
              title="No routes generated"
              hint={
                result.operational_vehicle_count === 0
                  ? "No operational vehicles with a depot are available."
                  : "Nothing was awaiting allocation."
              }
            />
          ) : (
            <Table head={["Vehicle", "Stops", "Distance", "ETA", "Groups"]}>
              {result.routes.map((route) => (
                <tr key={route.route_id}>
                  <td className="td font-mono text-xs">{shortId(route.vehicle_id)}</td>
                  <td className="td">{route.fulfillment_group_ids.length}</td>
                  <td className="td">{km(route.distance_m)}</td>
                  <td className="td">{minutes(route.travel_time_seconds)}</td>
                  <td className="td font-mono text-[11px] text-slate-500">
                    {route.fulfillment_group_ids.map(shortId).join("  ")}
                  </td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      )}

      <Card
        title="Persisted routes"
        action={
          <button className="btn text-xs" onClick={() => void routes.reload()}>
            Refresh
          </button>
        }
      >
        {routes.loading && <Loading label="Loading routes…" />}
        {routes.error !== null && <ErrorState error={routes.error} onRetry={routes.reload} />}
        {!routes.loading && routes.error === null && routeRows.length === 0 && (
          <EmptyState title="No routes yet" hint="Run the optimizer to create the first batch." />
        )}
        {routeRows.length > 0 && (
          <Table head={["Route", "Vehicle", "Status", "Stops", "Created"]}>
            {routeRows.slice(0, 12).map((route) => (
              <tr key={route.id}>
                <td className="td font-mono text-xs">{shortId(route.id)}</td>
                <td className="td font-mono text-xs">{shortId(route.vehicle_id)}</td>
                <td className="td">
                  <StatusBadge status={route.status} />
                </td>
                <td className="td">
                  {route.stops.filter((s) => s.status === "COMPLETED").length}/{route.stops.length}
                </td>
                <td className="td">{dateTime(route.created_at)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
