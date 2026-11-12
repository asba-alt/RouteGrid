import { useEffect, useMemo, useRef, useState } from "react";
import {
  Card,
  EmptyState,
  ErrorState,
  Loading,
  StatusBadge,
  Table,
} from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api, type InventoryRow, type OrderDetail, type Warehouse } from "../lib/api";
import { dateTime, kg, shortId } from "../lib/format";

const LIFECYCLE = [
  "PENDING_ALLOCATION",
  "ALLOCATED",
  "PICKING",
  "READY_FOR_DISPATCH",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
  "PARTIALLY_SHIPPED",
  "CANCELLED",
  "FAILED",
];

const NEXT_STATUS: Record<string, string> = {
  PENDING_ALLOCATION: "ALLOCATED",
  ALLOCATED: "PICKING",
  PICKING: "READY_FOR_DISPATCH",
  READY_FOR_DISPATCH: "OUT_FOR_DELIVERY",
};

const TERMINAL = new Set(["DELIVERED", "CANCELLED", "FAILED", "PARTIALLY_SHIPPED"]);

export default function OrdersPage() {
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<OrderDetail | null>(null);
  const [detailError, setDetailError] = useState<unknown>(null);

  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [warehouseId, setWarehouseId] = useState("");
  const [inventory, setInventory] = useState<InventoryRow[]>([]);
  const [sku, setSku] = useState("");
  const [inventoryError, setInventoryError] = useState<unknown>(null);

  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [formError, setFormError] = useState<unknown>(null);
  const [busyAction, setBusyAction] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null);

  const formRef = useRef<HTMLFormElement>(null);
  const orders = useAsync(() => api.orders(status || undefined), [status]);

  useEffect(() => {
    void api
      .warehouses(true)
      .then((rows) => {
        setWarehouses(rows);
        if (rows.length > 0) setWarehouseId((current) => current || rows[0].id);
      })
      .catch(() => setWarehouses([]));
  }, []);

  // Load real stock for the chosen warehouse so only orderable SKUs are offered.
  useEffect(() => {
    if (!warehouseId) {
      setInventory([]);
      return;
    }
    setInventoryError(null);
    setSku("");
    void api
      .inventory(warehouseId)
      .then((rows) => {
        setInventory(rows);
        const first = rows.find((row) => row.on_hand - row.reserved > 0);
        if (first) setSku(first.sku);
      })
      .catch((error) => {
        setInventory([]);
        setInventoryError(error);
      });
  }, [warehouseId]);

  const availableBySku = useMemo(() => {
    const map = new Map<string, number>();
    inventory.forEach((row) => map.set(row.sku, row.on_hand - row.reserved));
    return map;
  }, [inventory]);

  const selectedAvailable = sku ? (availableBySku.get(sku) ?? 0) : 0;

  const filtered = useMemo(() => {
    const rows = orders.data ?? [];
    if (!search.trim()) return rows;
    const needle = search.trim().toLowerCase();
    return rows.filter((order) => order.id.toLowerCase().includes(needle));
  }, [orders.data, search]);

  async function openDetail(id: string) {
    setDetailError(null);
    try {
      setSelected(await api.order(id));
    } catch (error) {
      setDetailError(error);
    }
  }

  async function submitIntake(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return; // duplicate-submission guard
    // React nulls event.currentTarget once the handler returns, so capture the
    // element *before* awaiting — otherwise reset() throws after a successful post.
    const form = event.currentTarget;
    const data = new FormData(form);
    const customerName = String(data.get("customer_name") ?? "").trim();
    const quantity = Number(data.get("quantity") ?? 0);
    const weight = String(data.get("weight_kg") ?? "1");

    setFormError(null);
    setNotice(null);

    if (!customerName) {
      setFormError(new Error("Enter the customer name."));
      return;
    }
    if (!warehouseId) {
      setFormError(new Error("Choose a warehouse first."));
      return;
    }
    if (!sku) {
      setFormError(new Error("This warehouse has no stock. Add inventory before ordering."));
      return;
    }
    if (quantity <= 0) {
      setFormError(new Error("Quantity must be greater than zero."));
      return;
    }
    if (quantity > selectedAvailable) {
      setFormError(
        new Error(`Only ${selectedAvailable} unit(s) of ${sku} available at this warehouse.`),
      );
      return;
    }

    setSubmitting(true);
    try {
      const result = await api.intakeOrder({
        warehouse_id: warehouseId,
        customer_name: customerName,
        delivery_location: { lat: 17.385, lng: 78.4867 },
        items: [{ sku, quantity, weight_kg: weight }],
      });
      setNotice(
        `Order ${result.reference ?? result.id.slice(0, 8)} for ${result.customer_name} created — ${result.reservations.length} reservation(s) placed. It is now listed below.`,
      );
      setHighlightId(result.id);
      window.setTimeout(() => setHighlightId(null), 6000);
      form.reset();
      setInventory(await api.inventory(warehouseId));
      await orders.reload();
    } catch (error) {
      setFormError(error);
    } finally {
      setSubmitting(false);
    }
  }

  async function changeStatus(id: string, next: string) {
    if (busyAction) return;
    setBusyAction(true);
    setNotice(null);
    setDetailError(null);
    try {
      await api.updateOrderStatus(id, next);
      setNotice(`Order moved to ${next.replaceAll("_", " ").toLowerCase()}.`);
      await orders.reload();
      setSelected(await api.order(id));
    } catch (error) {
      setDetailError(error);
    } finally {
      setBusyAction(false);
    }
  }

  return (
    <div className="space-y-5">
      <Card title="Create order (intake with inventory reservation)">
        <form ref={formRef} className="grid gap-4 md:grid-cols-2 lg:grid-cols-5" onSubmit={submitIntake}>
          <label className="block lg:col-span-2">
            <span className="label">Customer name</span>
            <input
              name="customer_name"
              className="input mt-1"
              placeholder="e.g. Sri Lakshmi Traders"
              autoComplete="off"
            />
          </label>

          <label className="block lg:col-span-2">
            <span className="label">Warehouse</span>
            <select
              className="input mt-1"
              value={warehouseId}
              onChange={(event) => setWarehouseId(event.target.value)}
            >
              {warehouses.length === 0 && <option value="">No operational warehouses</option>}
              {warehouses.map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouse.name}
                </option>
              ))}
            </select>
          </label>

          <label className="block lg:col-span-1">
            <span className="label">Item (SKU)</span>
            <select
              className="input mt-1"
              value={sku}
              onChange={(event) => setSku(event.target.value)}
            >
              {inventory.length === 0 && <option value="">No stock here</option>}
              {inventory.map((row) => (
                <option key={row.id} value={row.sku}>
                  {row.sku} — {row.on_hand - row.reserved} free
                </option>
              ))}
            </select>
          </label>

          <label className="block lg:col-span-1">
            <span className="label">Quantity</span>
            <input
              name="quantity"
              className="input mt-1"
              type="number"
              min={1}
              max={selectedAvailable || undefined}
              defaultValue={1}
            />
          </label>

          <label className="block lg:col-span-1">
            <span className="label">Unit weight (kg)</span>
            <input
              name="weight_kg"
              className="input mt-1"
              type="number"
              step="0.01"
              min={0}
              defaultValue="1.0"
            />
          </label>

          <div className="lg:col-span-5">
            <p className="mb-2 text-xs text-slate-500">
              {sku
                ? `${selectedAvailable} unit(s) of ${sku} in stock at this warehouse · total line weight = quantity × unit weight`
                : "Pick a warehouse with stock to begin."}
            </p>
            <button className="btn btn-primary" disabled={submitting || !sku}>
              {submitting ? "Placing order…" : "Place order"}
            </button>
          </div>
        </form>

        {inventoryError !== null && (
          <div className="mt-3">
            <ErrorState error={inventoryError} />
          </div>
        )}
        {notice && (
          <p className="mt-3 text-sm text-emerald-300" role="status">
            {notice}
          </p>
        )}
        {formError !== null && (
          <div className="mt-3">
            <p className="mb-1 text-sm font-medium text-rose-200">Could not create the order</p>
            <ErrorState error={formError} />
          </div>
        )}
      </Card>

      <Card
        title="Orders"
        action={
          <div className="flex gap-2">
            <input
              className="input w-44 py-1.5 text-xs"
              placeholder="Search by id…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <select
              className="input w-52 py-1.5 text-xs"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="">All statuses</option>
              {LIFECYCLE.map((state) => (
                <option key={state} value={state}>
                  {state}
                </option>
              ))}
            </select>
            <button className="btn text-xs" onClick={() => void orders.reload()}>
              Refresh
            </button>
          </div>
        }
      >
        {orders.loading && <Loading label="Loading orders…" />}
        {orders.error !== null && <ErrorState error={orders.error} onRetry={orders.reload} />}
        {!orders.loading && orders.error === null && filtered.length === 0 && (
          <EmptyState
            title="No orders match"
            hint="Adjust the filter, or create an order above."
          />
        )}
        {filtered.length > 0 && (
          <Table head={["Created", "Reference", "Customer", "Order", "Status", ""]}>
            {filtered.map((order) => (
              <tr
                key={order.id}
                className={
                  order.id === highlightId
                    ? "bg-indigo-500/10 ring-1 ring-inset ring-indigo-500/40"
                    : "hover:bg-slate-800/30"
                }
              >
                <td className="td">{dateTime(order.created_at)}</td>
                <td className="td font-mono text-xs text-slate-200">
                  {order.reference ?? shortId(order.id)}
                </td>
                <td className="td text-slate-200">{order.customer_name ?? "—"}</td>
                <td className="td font-mono text-xs text-slate-500">{shortId(order.id)}</td>
                <td className="td">
                  <StatusBadge status={order.status} />
                </td>
                <td className="td text-right">
                  <button
                    className="btn px-2 py-1 text-xs"
                    onClick={() => void openDetail(order.id)}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {detailError !== null && <ErrorState error={detailError} />}
      {selected && (
        <div
          className="fixed inset-0 z-[1000] flex justify-end bg-slate-950/70 backdrop-blur-sm"
          onClick={() => setSelected(null)}
        >
          <div
            className="h-full w-full max-w-2xl overflow-y-auto border-l border-panel-line bg-panel p-5 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
        <Card
          title={`${selected.reference ?? shortId(selected.id)} · ${selected.customer_name ?? "Unknown customer"}`}
          action={
            <div className="flex gap-2">
              {NEXT_STATUS[selected.status] && (
                <button
                  className="btn btn-primary text-xs"
                  disabled={busyAction}
                  onClick={() => void changeStatus(selected.id, NEXT_STATUS[selected.status])}
                >
                  Advance → {NEXT_STATUS[selected.status].replaceAll("_", " ").toLowerCase()}
                </button>
              )}
              {!TERMINAL.has(selected.status) && selected.status !== "OUT_FOR_DELIVERY" && (
                <button
                  className="btn text-xs"
                  disabled={busyAction}
                  onClick={() => void changeStatus(selected.id, "CANCELLED")}
                >
                  Cancel order
                </button>
              )}
              <button className="btn text-xs" onClick={() => setSelected(null)}>
                Close
              </button>
            </div>
          }
        >
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <p className="label">Status</p>
              <div className="mt-1">
                <StatusBadge status={selected.status} />
              </div>
            </div>
            <div>
              <p className="label">Created</p>
              <p className="mt-1 text-sm">{dateTime(selected.created_at)}</p>
            </div>
            <div>
              <p className="label">Delivery location</p>
              <p className="mt-1 font-mono text-xs">
                {selected.delivery_location
                  ? `${selected.delivery_location.lat.toFixed(4)}, ${selected.delivery_location.lng.toFixed(4)}`
                  : "—"}
              </p>
            </div>
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <div>
              <p className="label mb-2">Items</p>
              <Table head={["SKU", "Qty", "Unit weight"]}>
                {selected.items.map((item) => (
                  <tr key={item.id}>
                    <td className="td font-mono text-xs">{item.sku}</td>
                    <td className="td">{item.quantity}</td>
                    <td className="td">{kg(item.weight_kg)}</td>
                  </tr>
                ))}
              </Table>
            </div>
            <div>
              <p className="label mb-2">Inventory reservations</p>
              {selected.reservations.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No holds — this order was created without reserving stock.
                </p>
              ) : (
                <Table head={["SKU", "Reserved", "Warehouse"]}>
                  {selected.reservations.map((reservation) => (
                    <tr key={reservation.id}>
                      <td className="td font-mono text-xs">{reservation.sku}</td>
                      <td className="td">{reservation.quantity}</td>
                      <td className="td font-mono text-xs">
                        {shortId(reservation.warehouse_id)}
                      </td>
                    </tr>
                  ))}
                </Table>
              )}
            </div>
          </div>
        </Card>
          </div>
        </div>
      )}
    </div>
  );
}
