/**
 * Typed API client.
 *
 * Every failure surfaces as an ApiError carrying the backend's stable error
 * envelope (`{error: {code, message, request_id, details}}`), so the UI can show
 * a sensible message plus the correlation id without ever leaking internals.
 */
const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
// Optional shared API key. When the backend sets API_KEY, every request must
// carry it; when unset, the backend runs in development (open) mode.
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

export class ApiError extends Error {
  status: number;
  code: string;
  requestId?: string;
  details?: unknown;

  constructor(
    status: number,
    code: string,
    message: string,
    requestId?: string,
    details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }

  get isNetwork() {
    return this.status === 0;
  }
  get isUnavailable() {
    return this.status === 503 || this.status === 0;
  }
}

// ---------------------------------------------------------------- types

export type GeoPoint = { lat: number; lng: number };

export type Warehouse = {
  id: string;
  name: string;
  location: GeoPoint;
  operational: boolean;
};

export type InventoryRow = {
  id: string;
  warehouse_id: string;
  sku: string;
  on_hand: number;
  reserved: number;
};

export type WarehouseDetail = Warehouse & { inventory: InventoryRow[] };

export type Driver = { id: string; name: string | null };

export type Vehicle = {
  id: string;
  external_id: string | null;
  driver_id: string | null;
  depot_warehouse_id: string | null;
  max_weight_kg: string;
  operational: boolean;
};

export type VehicleDetail = Vehicle & { driver: Driver | null };

export type OrderItem = {
  id: string;
  order_id: string;
  sku: string;
  quantity: number;
  weight_kg: string;
};

export type Order = {
  id: string;
  customer_id: string | null;
  customer_name: string | null;
  reference: string | null;
  status: string;
  created_at: string;
};

export type Reservation = {
  id: string;
  warehouse_id: string;
  order_id: string;
  sku: string;
  quantity: number;
  expires_at: string | null;
};

export type OrderDetail = Order & {
  items: OrderItem[];
  delivery_location: GeoPoint | null;
  reservations: Reservation[];
};

export type OrderIntakeResult = OrderDetail & {
  warehouse_id: string;
  reservations: Reservation[];
};

export type PlannedRoute = {
  route_id: string;
  vehicle_id: string;
  fulfillment_group_ids: string[];
  distance_m: number;
  travel_time_seconds: number;
};

export type BatchSolveResult = {
  solved: boolean;
  routes: PlannedRoute[];
  unassigned_fulfillment_group_ids: string[];
  skipped_orders_without_location: number;
  eligible_order_count: number;
  operational_vehicle_count: number;
  total_distance_m: number;
  total_travel_time_seconds: number;
};

export type VehiclePosition = {
  route_id: string;
  vehicle_id: string | null;
  lat: number;
  lng: number;
  simulated_at: string;
  distance_travelled_m: number;
  total_distance_m: number;
  completed_stop_ids: string[];
  remaining_stop_ids: string[];
  finished: boolean;
  route_status: string;
  simulated: boolean;
};

export type AdvanceResult = {
  advanced: VehiclePosition[];
  skipped_routes: number;
};

export type RouteStopRow = {
  id: string;
  sequence: number;
  status: string;
  fulfillment_group_id: string;
  lat: number | null;
  lng: number | null;
  arrived_at: string | null;
};

export type RouteRow = {
  id: string;
  vehicle_id: string | null;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  stops: RouteStopRow[];
};

export type Disruption = {
  id: string;
  kind: string;
  status: string;
  vehicle_id: string | null;
  route_id: string | null;
  description: string | null;
  affected_group_ids: { group_ids?: string[] } | null;
  resolution: string | null;
  created_at: string;
  resolved_at: string | null;
};

export type DisruptionImpact = {
  disruption: Disruption;
  released_group_ids: string[];
  preserved_completed_stop_ids: string[];
  route_status: string | null;
  vehicle_operational: boolean | null;
  reoptimized_routes: number;
  reoptimized_reason: string | null;
};

export type Health = {
  status: string;
  database: string;
  redis: string;
};

// ---------------------------------------------------------------- transport

async function rawRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      0,
      "network_error",
      "Cannot reach the RouteGrid API. Check that the backend is running.",
    );
  }

  if (!response.ok) {
    let code = "error";
    let message = `Request failed (${response.status})`;
    let requestId: string | undefined;
    let details: unknown;
    try {
      const body = await response.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        requestId = body.error.request_id ?? undefined;
        details = body.error.details ?? undefined;
      } else if (typeof body?.detail === "string") {
        message = body.detail;
      }
    } catch {
      /* non-JSON error body: keep the generic message */
    }
    throw new ApiError(response.status, code, message, requestId, details);
  }

  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Retries only safe (idempotent) reads, and only for transient failures.
 * Mutating calls never retry automatically.
 */
async function get<T>(path: string, attempts = 3): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await rawRequest<T>(path);
    } catch (error) {
      lastError = error;
      const retryable =
        error instanceof ApiError && (error.isUnavailable || error.status >= 500);
      if (!retryable || attempt === attempts - 1) throw error;
      await sleep(300 * 2 ** attempt);
    }
  }
  throw lastError;
}

// ---------------------------------------------------------------- endpoints

const qs = (params: Record<string, string | number | boolean | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== "") search.set(k, String(v));
  });
  const s = search.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => get<Health>("/health"),

  warehouses: (operational?: boolean) =>
    get<Warehouse[]>(`/api/v1/warehouses${qs({ operational })}`),
  warehouse: (id: string) => get<WarehouseDetail>(`/api/v1/warehouses/${id}`),
  inventory: (id: string) =>
    get<InventoryRow[]>(`/api/v1/warehouses/${id}/inventory`),
  createWarehouse: (body: { name: string; location: GeoPoint; operational?: boolean }) =>
    rawRequest<Warehouse>("/api/v1/warehouses", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateWarehouse: (id: string, body: { name?: string; operational?: boolean }) =>
    rawRequest<Warehouse>(`/api/v1/warehouses/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  upsertInventory: (
    warehouseId: string,
    sku: string,
    body: { on_hand: number; reserved?: number },
  ) =>
    rawRequest<InventoryRow>(
      `/api/v1/warehouses/${warehouseId}/inventory/${encodeURIComponent(sku)}`,
      { method: "PUT", body: JSON.stringify(body) },
    ),

  drivers: () => get<Driver[]>("/api/v1/drivers"),
  createDriver: (body: { name?: string }) =>
    rawRequest<Driver>("/api/v1/drivers", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  vehicles: (operational?: boolean) =>
    get<Vehicle[]>(`/api/v1/vehicles${qs({ operational })}`),
  vehicle: (id: string) => get<VehicleDetail>(`/api/v1/vehicles/${id}`),
  createVehicle: (body: Record<string, unknown>) =>
    rawRequest<Vehicle>("/api/v1/vehicles", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateVehicle: (id: string, body: Record<string, unknown>) =>
    rawRequest<Vehicle>(`/api/v1/vehicles/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  orders: (status?: string) =>
    get<Order[]>(`/api/v1/orders${qs({ status })}`),
  order: (id: string) => get<OrderDetail>(`/api/v1/orders/${id}`),
  createOrder: (body: Record<string, unknown>) =>
    rawRequest<OrderDetail>("/api/v1/orders", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  intakeOrder: (body: {
    warehouse_id: string;
    customer_id?: string;
    customer_name?: string;
    delivery_location?: GeoPoint;
    items: { sku: string; quantity: number; weight_kg: string }[];
  }) =>
    rawRequest<OrderIntakeResult>("/api/v1/orders/intake", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateOrderStatus: (id: string, status: string) =>
    rawRequest<Order>(`/api/v1/orders/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  optimize: (body: { time_limit_seconds?: number; use_local_search?: boolean } = {}) =>
    rawRequest<BatchSolveResult>("/api/v1/optimization/solve", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  routes: (status?: string) => get<RouteRow[]>(`/api/v1/routes${qs({ status })}`),
  route: (id: string) => get<RouteRow>(`/api/v1/routes/${id}`),

  advance: (body: { elapsed_seconds: number; route_id?: string }) =>
    rawRequest<AdvanceResult>("/api/v1/simulation/advance", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  positions: () => get<VehiclePosition[]>("/api/v1/simulation/positions"),

  disruptions: (status?: string) =>
    get<Disruption[]>(`/api/v1/disruptions${qs({ status })}`),
  reportDisruption: (body: Record<string, unknown>) =>
    rawRequest<DisruptionImpact>("/api/v1/disruptions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  resolveDisruption: (id: string, body: { resolution?: string; reoptimize?: boolean }) =>
    rawRequest<DisruptionImpact>(`/api/v1/disruptions/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
