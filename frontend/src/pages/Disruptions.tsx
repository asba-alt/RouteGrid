import { useEffect, useState } from "react";
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
import { api, type RouteRow } from "../lib/api";
import { dateTime, shortId } from "../lib/format";

const KINDS = [
  "VEHICLE_BREAKDOWN",
  "TRAFFIC_DELAY",
  "VEHICLE_UNAVAILABLE",
  "DELIVERY_FAILURE",
  "OTHER",
];

export default function DisruptionsPage() {
  const disruptions = useAsync(() => api.disruptions(), []);
  const [routes, setRoutes] = useState<RouteRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [lastImpact, setLastImpact] = useState<string | null>(null);

  useEffect(() => {
    void api
      .routes()
      .then((rows) => setRoutes(rows.filter((r) => ["PLANNED", "IN_PROGRESS"].includes(r.status))))
      .catch(() => setRoutes([]));
  }, []);

  async function report(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const formEl = event.currentTarget;
    const form = new FormData(formEl);
    const routeId = String(form.get("route_id") ?? "");
    const kind = String(form.get("kind") ?? "VEHICLE_BREAKDOWN");
    const description = String(form.get("description") ?? "").trim() || undefined;
    setBusy(true);
    setError(null);
    setNotice(null);
    setLastImpact(null);
    try {
      const impact = await api.reportDisruption({ kind, route_id: routeId, description });
      setNotice(`Disruption recorded (${impact.disruption.status}).`);
      setLastImpact(
        `Route ${impact.route_status ?? "unchanged"} · ${impact.released_group_ids.length} delivery group(s) released · ${impact.preserved_completed_stop_ids.length} completed stop(s) preserved`,
      );
      formEl.reset();
      await disruptions.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function resolve(id: string, reoptimize: boolean) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const impact = await api.resolveDisruption(id, {
        reoptimize,
        resolution: reoptimize ? "Re-optimized from dashboard" : "Closed from dashboard",
      });
      setNotice(
        reoptimize
          ? `Resolved and re-optimized into ${impact.reoptimized_routes} route(s).`
          : "Disruption closed.",
      );
      if (impact.reoptimized_reason) setError(new Error(impact.reoptimized_reason));
      await disruptions.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const rows = disruptions.data ?? [];
  const open = rows.filter((d) => d.status !== "RESOLVED").length;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total incidents" value={rows.length} />
        <StatCard label="Open" value={open} tone={open ? "warn" : "good"} />
        <StatCard label="Resolved" value={rows.length - open} tone="good" />
        <StatCard
          label="Active routes"
          value={routes.length}
          hint="Candidates for disruption"
        />
      </div>

      <Card title="Report disruption">
        <form className="grid gap-3 md:grid-cols-4" onSubmit={report}>
          <select name="kind" className="input md:col-span-2" defaultValue="VEHICLE_BREAKDOWN">
            {KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {kind.replaceAll("_", " ")}
              </option>
            ))}
          </select>
          <select name="route_id" className="input md:col-span-2" defaultValue="">
            <option value="">Select an active route…</option>
            {routes.map((r) => (
              <option key={r.id} value={r.id}>
                {shortId(r.id)} · {r.status} · {r.stops.length} stops
              </option>
            ))}
          </select>
          <input
            name="description"
            className="input md:col-span-4"
            placeholder="Optional description"
          />
          <div className="md:col-span-4">
            <button className="btn btn-primary" disabled={busy || routes.length === 0}>
              {busy ? "Recording…" : "Report disruption"}
            </button>
            {routes.length === 0 && (
              <span className="ml-3 text-xs text-slate-500">
                Run the optimizer first so there is a route to disrupt.
              </span>
            )}
          </div>
        </form>
        {notice && <p className="mt-2 text-sm text-emerald-300">{notice}</p>}
        {lastImpact && <p className="mt-1 text-xs text-slate-400">{lastImpact}</p>}
        {error !== null && <div className="mt-2"><ErrorState error={error} /></div>}
      </Card>

      <Card
        title="Incident history"
        action={
          <button className="btn text-xs" onClick={() => void disruptions.reload()}>
            Refresh
          </button>
        }
      >
        {disruptions.loading && <Loading label="Loading incidents…" />}
        {disruptions.error !== null && (
          <ErrorState error={disruptions.error} onRetry={disruptions.reload} />
        )}
        {!disruptions.loading && disruptions.error === null && rows.length === 0 && (
          <EmptyState title="No incidents recorded" hint="Reported disruptions will appear here with their resolution." />
        )}
        {rows.length > 0 && (
          <Table head={["When", "Kind", "Status", "Route", "Released", "Resolution", ""]}>
            {rows.map((d) => (
              <tr key={d.id}>
                <td className="td">{dateTime(d.created_at)}</td>
                <td className="td text-xs">{d.kind.replaceAll("_", " ")}</td>
                <td className="td">
                  <StatusBadge status={d.status} />
                </td>
                <td className="td font-mono text-xs">{shortId(d.route_id)}</td>
                <td className="td">{d.affected_group_ids?.group_ids?.length ?? 0}</td>
                <td className="td max-w-[220px] truncate text-xs text-slate-400">
                  {d.resolution ?? "—"}
                </td>
                <td className="td text-right">
                  {d.status !== "RESOLVED" && (
                    <div className="flex justify-end gap-1">
                      <button
                        className="btn px-2 py-1 text-[11px]"
                        onClick={() => void resolve(d.id, false)}
                        disabled={busy}
                      >
                        Close
                      </button>
                      <button
                        className="btn btn-primary px-2 py-1 text-[11px]"
                        onClick={() => void resolve(d.id, true)}
                        disabled={busy}
                      >
                        Resolve + re-optimize
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
