import { useEffect, useMemo, useState } from "react";
import { MapBox, type MapLine, type MapMarker } from "../components/MapBox";
import { Card, EmptyState, ErrorState, Loading, Progress } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api, type VehiclePosition } from "../lib/api";
import { dateTime, km, shortId, titleCase } from "../lib/format";

const HYDERABAD: [number, number] = [17.385, 78.4867];
const ACTIVE = new Set(["PLANNED", "IN_PROGRESS"]);

export default function TrackingPage() {
  const routes = useAsync(() => api.routes(), []);
  const [positions, setPositions] = useState<VehiclePosition[]>([]);
  const [elapsed, setElapsed] = useState(5);
  const [busy, setBusy] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [lastAdvance, setLastAdvance] = useState<Date | null>(null);
  const [positionsError, setPositionsError] = useState<unknown>(null);

  // Show where every active vehicle is straight away, then keep it fresh.
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const current = await api.positions();
        if (!cancelled) {
          setPositions(current);
          setPositionsError(null);
        }
      } catch (err) {
        // Keep the last good positions on screen; surface the problem separately.
        if (!cancelled) setPositionsError(err);
      }
    };
    void load();
    const timer = window.setInterval(load, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const activeRoutes = useMemo(
    () => (routes.data ?? []).filter((route) => ACTIVE.has(route.status)),
    [routes.data],
  );

  const byRoute = useMemo(
    () => new Map(activeRoutes.map((route) => [route.id, route])),
    [activeRoutes],
  );

  const markers: MapMarker[] = [];
  const lines: MapLine[] = [];

  activeRoutes.forEach((route) => {
    const points = route.stops
      .filter((stop) => stop.lat !== null && stop.lng !== null)
      .map((stop) => [stop.lat as number, stop.lng as number] as [number, number]);

    // Two or more stops gives a real polyline; one stop still gets a marker below.
    if (points.length > 1) {
      lines.push({ id: route.id, points, tone: "planned" });
    }
    route.stops.forEach((stop) => {
      if (stop.lat === null || stop.lng === null) return;
      markers.push({
        id: `stop-${stop.id}`,
        lat: stop.lat,
        lng: stop.lng,
        label: `Stop ${stop.sequence}`,
        detail: titleCase(stop.status),
        tone: stop.status === "COMPLETED" ? "done" : "stop",
      });
    });
  });

  positions.forEach((position) => {
    if (!Number.isFinite(position.lat) || !Number.isFinite(position.lng)) return;
    markers.push({
      id: `vehicle-${position.route_id}`,
      lat: position.lat,
      lng: position.lng,
      label: `Vehicle ${shortId(position.vehicle_id)}`,
      detail: `${position.completed_stop_ids.length} stop(s) done · ${titleCase(position.route_status)}`,
      tone: "vehicle",
    });
  });

  async function advance() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const outcome = await api.advance({ elapsed_seconds: elapsed });
      setPositions((previous) => {
        const merged = new Map(previous.map((p) => [p.route_id, p]));
        outcome.advanced.forEach((p) => {
          if (Number.isFinite(p.lat) && Number.isFinite(p.lng)) merged.set(p.route_id, p);
        });
        return Array.from(merged.values());
      });
      setLastAdvance(new Date());
      await routes.reload();
    } catch (err) {
      setError(err);
      setPlaying(false);
    } finally {
      setBusy(false);
    }
  }

  // Auto-play advances on a fixed cadence; the effect re-arms when the step
  // size changes so the newest value is used.
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      void advance();
    }, 2500);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, elapsed]);

  return (
    <div className="space-y-5">
      <Card
        title="GPS simulator"
        action={<span className="text-xs text-slate-500">Simulated telemetry — not hardware GPS</span>}
      >
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-slate-400">
            Step size (real seconds)
            <input
              className="input mt-1 w-32"
              type="number"
              min={1}
              step={1}
              value={elapsed}
              onChange={(event) => setElapsed(Number(event.target.value))}
            />
          </label>
          <button className="btn btn-primary" onClick={() => void advance()} disabled={busy || playing}>
            {busy ? "Stepping…" : "Advance simulation"}
          </button>
          <button className="btn" onClick={() => setPlaying((value) => !value)}>
            {playing ? "Pause live" : "Play live"}
          </button>
          {lastAdvance && (
            <span className="text-xs text-slate-500">last step {lastAdvance.toLocaleTimeString()}</span>
          )}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          {elapsed}s real → {elapsed * 60}s simulated (×60 compression), ≈{" "}
          {km(Math.round((elapsed * 60 * 40 * 1000) / 3600))} at 40 km/h. Positions refresh
          every 5s.
        </p>
        {error !== null && (
          <div className="mt-3">
            <ErrorState error={error} onRetry={advance} />
          </div>
        )}
      </Card>

      <Card
        title={`Live map · ${activeRoutes.length} active route(s)`}
        action={
          <button className="btn text-xs" onClick={() => void routes.reload()}>
            Refresh
          </button>
        }
      >
        {routes.loading && <Loading label="Loading route geometry…" />}
        {routes.error !== null && <ErrorState error={routes.error} onRetry={routes.reload} />}
        {!routes.loading && routes.error === null && activeRoutes.length === 0 && (
          <EmptyState
            title="No active routes"
            hint="Run the optimizer to create routes, then press Play live to watch vehicles move."
          />
        )}
        {activeRoutes.length > 0 && (
          <MapBox
            center={HYDERABAD}
            zoom={11}
            height="520px"
            markers={markers}
            lines={lines}
          />
        )}
        {positionsError !== null && (
          <p className="mt-2 text-xs text-amber-300">
            Could not refresh positions — showing the last known values.
          </p>
        )}
      </Card>

      {positions.length > 0 && (
        <Card title="Vehicle progress">
          <div className="space-y-4">
            {positions.map((position) => {
              const totalStops = byRoute.get(position.route_id)?.stops.length ?? 0;
              const pct =
                position.total_distance_m === 0
                  ? totalStops === 0
                    ? 0
                    : (position.completed_stop_ids.length / totalStops) * 100
                  : Math.min(100, (position.distance_travelled_m / position.total_distance_m) * 100);
              return (
                <div key={position.route_id}>
                  <div className="mb-1 flex items-center justify-between text-xs text-slate-400">
                    <span className="font-mono">
                      {shortId(position.vehicle_id)} · {totalStops} stops
                    </span>
                    <span>
                      {position.completed_stop_ids.length}/{totalStops} done · {titleCase(position.route_status)}
                    </span>
                  </div>
                  <Progress value={pct} />
                  <p className="mt-1 text-[11px] text-slate-500">
                    simulated {dateTime(position.simulated_at)} · {km(position.distance_travelled_m)} of{" "}
                    {km(position.total_distance_m)} · {position.finished ? "finished" : "in progress"}
                  </p>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}
