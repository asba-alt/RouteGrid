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
import { api, type WarehouseDetail } from "../lib/api";

const LOW_STOCK_THRESHOLD = 20;

export default function WarehousesPage() {
  const warehouses = useAsync(() => api.warehouses(), []);
  const [selected, setSelected] = useState<WarehouseDetail | null>(null);
  const [detailError, setDetailError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [formError, setFormError] = useState<unknown>(null);
  const [stockSearch, setStockSearch] = useState("");
  const [lowOnly, setLowOnly] = useState(false);

  async function open(id: string) {
    setDetailError(null);
    try {
      setSelected(await api.warehouse(id));
    } catch (error) {
      setDetailError(error);
    }
  }

  async function createWarehouse(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const formEl = event.currentTarget;
    const form = new FormData(formEl);
    const name = String(form.get("name") ?? "").trim();
    const lat = Number(form.get("lat"));
    const lng = Number(form.get("lng"));
    setFormError(null);
    setNotice(null);
    if (name.length < 2) {
      setFormError(new Error("Warehouse name must be at least 2 characters."));
      return;
    }
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
      setFormError(new Error("Enter a valid latitude (−90…90) and longitude (−180…180)."));
      return;
    }
    setBusy(true);
    try {
      const created = await api.createWarehouse({ name, location: { lat, lng } });
      setNotice(`Created warehouse ${created.name}.`);
      formEl.reset();
      await warehouses.reload();
    } catch (error) {
      setFormError(error);
    } finally {
      setBusy(false);
    }
  }

  async function upsertStock(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || busy) return;
    const form = new FormData(event.currentTarget);
    const sku = String(form.get("sku") ?? "").trim();
    const onHand = Number(form.get("on_hand"));
    setFormError(null);
    setNotice(null);
    if (!sku || onHand < 0) {
      setFormError(new Error("Provide a SKU and a non-negative on-hand quantity."));
      return;
    }
    setBusy(true);
    try {
      await api.upsertInventory(selected.id, sku, { on_hand: onHand });
      setNotice(`Stock for ${sku} set to ${onHand}.`);
      await open(selected.id);
    } catch (error) {
      setFormError(error);
    } finally {
      setBusy(false);
    }
  }

  async function toggleOperational(id: string, operational: boolean) {
    setFormError(null);
    try {
      await api.updateWarehouse(id, { operational });
      await warehouses.reload();
      if (selected?.id === id) await open(id);
    } catch (error) {
      setFormError(error);
    }
  }

  const visibleInventory = selected
    ? selected.inventory.filter((row) => {
        const matches = row.sku
          .toLowerCase()
          .includes(stockSearch.trim().toLowerCase());
        const isLow = row.on_hand - row.reserved <= LOW_STOCK_THRESHOLD;
        return matches && (!lowOnly || isLow);
      })
    : [];

  const rows = warehouses.data ?? [];

  return (
    <div className="space-y-5">
      <Card title="Register warehouse">
        <form className="grid gap-3 md:grid-cols-4" onSubmit={createWarehouse}>
          <input name="name" className="input md:col-span-2" placeholder="Warehouse name" />
          <input name="lat" className="input" type="number" step="0.0001" defaultValue="17.3850" placeholder="Latitude" />
          <input name="lng" className="input" type="number" step="0.0001" defaultValue="78.4867" placeholder="Longitude" />
          <div className="md:col-span-4">
            <button className="btn btn-primary" disabled={busy}>
              {busy ? "Saving…" : "Create warehouse"}
            </button>
          </div>
        </form>
        {notice && <p className="mt-2 text-sm text-emerald-300">{notice}</p>}
        {formError !== null && <div className="mt-2"><ErrorState error={formError} /></div>}
      </Card>

      <Card
        title="Warehouses"
        action={
          <button className="btn text-xs" onClick={() => void warehouses.reload()}>
            Refresh
          </button>
        }
      >
        {warehouses.loading && <Loading label="Loading warehouses…" />}
        {warehouses.error !== null && (
          <ErrorState error={warehouses.error} onRetry={warehouses.reload} />
        )}
        {!warehouses.loading && warehouses.error === null && rows.length === 0 && (
          <EmptyState title="No warehouses registered" hint="Create one above to start receiving orders." />
        )}
        {rows.length > 0 && (
          <Table head={["Name", "Location", "Operational", ""]}>
            {rows.map((w) => (
              <tr key={w.id} className="hover:bg-slate-800/30">
                <td className="td font-medium text-slate-200">{w.name}</td>
                <td className="td font-mono text-xs">
                  {w.location.lat.toFixed(4)}, {w.location.lng.toFixed(4)}
                </td>
                <td className="td">
                  <StatusBadge status={w.operational ? "COMPLETED" : "CANCELLED"} />
                </td>
                <td className="td text-right">
                  <div className="flex justify-end gap-1">
                    <button
                      className="btn px-2 py-1 text-xs"
                      onClick={() => void toggleOperational(w.id, !w.operational)}
                    >
                      {w.operational ? "Take offline" : "Bring online"}
                    </button>
                    <button className="btn px-2 py-1 text-xs" onClick={() => void open(w.id)}>
                      Inventory
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {detailError !== null && <ErrorState error={detailError} />}
      {selected && (
        <Card
          title={`Inventory — ${selected.name}`}
          action={
            <button className="btn text-xs" onClick={() => setSelected(null)}>
              Close
            </button>
          }
        >
          <form className="mb-4 grid gap-3 md:grid-cols-4" onSubmit={upsertStock}>
            <input name="sku" className="input md:col-span-2" placeholder="SKU" />
            <input name="on_hand" className="input" type="number" min={0} defaultValue={0} />
            <button className="btn btn-primary" disabled={busy}>
              Set stock
            </button>
          </form>

          <div className="mb-3 flex flex-wrap items-center gap-3">
            <input
              className="input w-56 py-1.5 text-xs"
              placeholder="Filter SKUs…"
              value={stockSearch}
              onChange={(event) => setStockSearch(event.target.value)}
            />
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <input
                type="checkbox"
                checked={lowOnly}
                onChange={(event) => setLowOnly(event.target.checked)}
              />
              Low stock only (≤ {LOW_STOCK_THRESHOLD})
            </label>
            <span className="text-xs text-slate-500">
              {visibleInventory.length} of {selected.inventory.length} SKUs
            </span>
          </div>

          {visibleInventory.length === 0 ? (
            <EmptyState
              title={lowOnly ? "No low-stock SKUs" : "No inventory recorded"}
              hint={
                lowOnly
                  ? "Everything is above the low-stock threshold."
                  : "Add stock using the form above."
              }
            />
          ) : (
            <Table head={["SKU", "On hand", "Reserved", "Available"]}>
              {visibleInventory.map((row) => {
                const available = row.on_hand - row.reserved;
                const low = available <= LOW_STOCK_THRESHOLD;
                return (
                  <tr key={row.id}>
                    <td className="td font-mono text-xs">{row.sku}</td>
                    <td className="td">{row.on_hand}</td>
                    <td className="td">{row.reserved}</td>
                    <td className={`td font-semibold ${low ? "text-amber-300" : "text-emerald-300"}`}>
                      {available}
                      {low && (
                        <span className="ml-2 rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px]">
                          low
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </Table>
          )}
        </Card>
      )}
    </div>
  );
}
