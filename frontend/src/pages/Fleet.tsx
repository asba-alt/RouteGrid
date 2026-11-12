import { useState } from "react";
import {
  Card,
  EmptyState,
  ErrorState,
  Loading,
  StatusBadge,
  Table,
} from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api } from "../lib/api";
import { kg, shortId } from "../lib/format";

export default function FleetPage() {
  const drivers = useAsync(() => api.drivers(), []);
  const vehicles = useAsync(() => api.vehicles(), []);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function addDriver(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const formEl = event.currentTarget;
    const form = new FormData(formEl);
    const name = String(form.get("name") ?? "").trim();
    if (!name) {
      setError(new Error("Driver name is required."));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.createDriver({ name });
      setNotice(`Driver ${name} added.`);
      formEl.reset();
      await drivers.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function addVehicle(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const formEl = event.currentTarget;
    const form = new FormData(formEl);
    const payload = {
      external_id: String(form.get("external_id") ?? "").trim() || undefined,
      driver_id: String(form.get("driver_id") ?? "") || undefined,
      depot_warehouse_id: String(form.get("depot_warehouse_id") ?? "") || undefined,
      max_weight_kg: String(form.get("max_weight_kg") ?? "500"),
      operational: true,
    };
    setBusy(true);
    setError(null);
    try {
      await api.createVehicle(payload);
      setNotice("Vehicle registered.");
      formEl.reset();
      await vehicles.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function toggleOperational(id: string, operational: boolean) {
    try {
      await api.updateVehicle(id, { operational });
      await vehicles.reload();
    } catch (err) {
      setError(err);
    }
  }

  const driversList = drivers.data ?? [];
  const vehicleList = vehicles.data ?? [];

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Add driver">
          <form className="flex gap-3" onSubmit={addDriver}>
            <input name="name" className="input" placeholder="Driver name" />
            <button className="btn btn-primary shrink-0" disabled={busy}>
              Add
            </button>
          </form>
        </Card>

        <Card title="Register vehicle">
          <form className="grid gap-3 md:grid-cols-2" onSubmit={addVehicle}>
            <input name="external_id" className="input" placeholder="External id e.g. VH-099" />
            <input
              name="max_weight_kg"
              className="input"
              type="number"
              step="0.01"
              min={0}
              defaultValue="500"
              placeholder="Capacity kg"
            />
            <select name="driver_id" className="input" defaultValue="">
              <option value="">No driver</option>
              {driversList.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name ?? d.id.slice(0, 8)}
                </option>
              ))}
            </select>
            <select name="depot_warehouse_id" className="input" defaultValue="">
              <option value="">No depot</option>
              {Array.from(
                new Map(
                  vehicleList
                    .filter((v) => v.depot_warehouse_id)
                    .map((v) => [v.depot_warehouse_id as string, v.depot_warehouse_id as string]),
                ),
              ).map(([id]) => (
                <option key={id} value={id}>
                  {shortId(id)}
                </option>
              ))}
            </select>
            <div className="md:col-span-2">
              <button className="btn btn-primary" disabled={busy}>
                Register vehicle
              </button>
            </div>
          </form>
        </Card>
      </div>

      {notice && <p className="text-sm text-emerald-300">{notice}</p>}
      {error !== null && <ErrorState error={error} />}

      <Card title="Drivers">
        {drivers.loading && <Loading />}
        {drivers.error !== null && <ErrorState error={drivers.error} onRetry={drivers.reload} />}
        {!drivers.loading && drivers.error === null && driversList.length === 0 && (
          <EmptyState title="No drivers" hint="Add a driver to start assigning vehicles." />
        )}
        {driversList.length > 0 && (
          <Table head={["Name", "Id"]}>
            {driversList.map((d) => (
              <tr key={d.id}>
                <td className="td">{d.name ?? "—"}</td>
                <td className="td font-mono text-xs">{shortId(d.id)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Card
        title="Vehicles"
        action={
          <button className="btn text-xs" onClick={() => void vehicles.reload()}>
            Refresh
          </button>
        }
      >
        {vehicles.loading && <Loading />}
        {vehicles.error !== null && <ErrorState error={vehicles.error} onRetry={vehicles.reload} />}
        {!vehicles.loading && vehicles.error === null && vehicleList.length === 0 && (
          <EmptyState title="No vehicles" hint="Register a vehicle so optimization has capacity to use." />
        )}
        {vehicleList.length > 0 && (
          <Table head={["Vehicle", "Capacity", "Driver", "Depot", "State", ""]}>
            {vehicleList.map((v) => (
              <tr key={v.id}>
                <td className="td font-mono text-xs">{v.external_id ?? shortId(v.id)}</td>
                <td className="td">{kg(v.max_weight_kg)}</td>
                <td className="td font-mono text-xs">{shortId(v.driver_id)}</td>
                <td className="td font-mono text-xs">{shortId(v.depot_warehouse_id)}</td>
                <td className="td">
                  <StatusBadge status={v.operational ? "COMPLETED" : "CANCELLED"} />
                </td>
                <td className="td text-right">
                  <button
                    className="btn px-2 py-1 text-xs"
                    onClick={() => void toggleOperational(v.id, !v.operational)}
                  >
                    {v.operational ? "Take offline" : "Bring online"}
                  </button>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
