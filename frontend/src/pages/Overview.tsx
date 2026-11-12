import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, ErrorState, Loading, StatCard, StatusBadge, Table } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { api } from "../lib/api";
import { dateTime, titleCase } from "../lib/format";

export default function OverviewPage() {
  const { data, error, loading, reload } = useAsync(
    () =>
      Promise.all([api.orders(), api.vehicles(), api.warehouses(), api.routes()]),
    [],
  );

  const stats = useMemo(() => {
    if (!data) return null;
    const [orders, vehicles, warehouses, routes] = data;
    const byStatus = orders.reduce<Record<string, number>>((acc, o) => {
      acc[o.status] = (acc[o.status] ?? 0) + 1;
      return acc;
    }, {});
    const activeRoutes = routes.filter((r) =>
      ["PLANNED", "IN_PROGRESS"].includes(r.status),
    );
    const operational = vehicles.filter((v) => v.operational);
    const assignedStops = activeRoutes.reduce(
      (sum, r) => sum + r.stops.filter((s) => s.status !== "COMPLETED").length,
      0,
    );
    return {
      orders,
      byStatus,
      total: orders.length,
      pending: byStatus.PENDING_ALLOCATION ?? 0,
      delivered: byStatus.DELIVERED ?? 0,
      activeRoutes: activeRoutes.length,
      activeVehicles: operational.length,
      totalVehicles: vehicles.length,
      warehouses: warehouses.length,
      operationalWarehouses: warehouses.filter((w) => w.operational).length,
      unassigned: assignedStops,
      utilization:
        vehicles.length === 0
          ? 0
          : Math.round((activeRoutes.length / vehicles.length) * 100),
    };
  }, [data]);

  if (loading) return <Loading label="Loading operational overview…" />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!stats) return null;

  const chartData = Object.entries(stats.byStatus).map(([status, count]) => ({
    status: titleCase(status),
    count,
  }));

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total orders" value={stats.total} hint="All time" />
        <StatCard
          label="Pending allocation"
          value={stats.pending}
          tone={stats.pending > 0 ? "warn" : "default"}
          hint="Awaiting the next batch solve"
        />
        <StatCard
          label="Delivered"
          value={stats.delivered}
          tone="good"
          hint="Completed orders"
        />
        <StatCard
          label="Unassigned stops"
          value={stats.unassigned}
          tone={stats.unassigned > 0 ? "warn" : "good"}
          hint="Open stops across active routes"
        />
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Active routes" value={stats.activeRoutes} />
        <StatCard
          label="Active vehicles"
          value={`${stats.activeVehicles}/${stats.totalVehicles}`}
        />
        <StatCard
          label="Fleet utilisation"
          value={`${stats.utilization}%`}
          tone={stats.utilization > 90 ? "warn" : "default"}
          hint="Active routes ÷ vehicles"
        />
        <StatCard
          label="Warehouses online"
          value={`${stats.operationalWarehouses}/${stats.warehouses}`}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Orders by lifecycle state">
          {chartData.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-500">No orders yet.</p>
          ) : (
            <div style={{ height: 260 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid stroke="#1f2b45" vertical={false} />
                  <XAxis
                    dataKey="status"
                    tick={{ fill: "#94a3b8", fontSize: 11 }}
                    interval={0}
                    angle={-20}
                    textAnchor="end"
                    height={70}
                  />
                  <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      background: "#0f172a",
                      border: "1px solid #1f2b45",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card title="Most recent orders">
          <Table head={["Created", "Order", "Status"]}>
            {stats.orders.slice(0, 8).map((order) => (
              <tr key={order.id}>
                <td className="td">{dateTime(order.created_at)}</td>
                <td className="td font-mono text-xs">{order.id.slice(0, 8)}…</td>
                <td className="td">
                  <StatusBadge status={order.status} />
                </td>
              </tr>
            ))}
            {stats.orders.length === 0 && (
              <tr>
                <td className="td text-slate-500" colSpan={3}>
                  No orders yet — create one from the Orders page.
                </td>
              </tr>
            )}
          </Table>
        </Card>
      </div>
    </div>
  );
}
