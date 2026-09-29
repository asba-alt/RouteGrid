# Database: Schema Guidance and Migration Notes

This document records schema guidance and example DDL for RouteGrid v1. It is intended as a migration-first reference for implementers and reviewers. Do not treat these DDL snippets as production-ready — they are a clear, reviewable starting point for Alembic or other migration scripts.

Principles

- PostgreSQL (with PostGIS) is the canonical store for all durable domain state.
- Redis is used only as a cache for current simulated vehicle positions.
- Every meaningful state change must write an outbox row in the same Postgres transaction as the state change.
- Inventory correctness is implemented via explicit reservation/hold rows, not by opportunistically decrementing on-hand quantities.
- The schema should support auditability and replays: persist routes, assignment history, telemetry snapshots, and outbox events.

Naming conventions

- Tables are snake_case.
- Primary keys are `id` (UUID) where feasible to simplify distributed references later.
- Timestamp columns use `timestamptz` and default to `now()`.
- JSON payloads use `jsonb`.

Example DDL (review and convert into migrations)

-- Extensions

CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Outbox table (transactional event log)

CREATE TABLE IF NOT EXISTS outbox_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at timestamptz NOT NULL DEFAULT now(),
    aggregate_type text NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    published boolean NOT NULL DEFAULT false,
    published_at timestamptz NULL,
    metadata jsonb NULL
);

CREATE INDEX IF NOT EXISTS idx_outbox_published ON outbox_event (published, occurred_at);

-- 2. Orders and items

CREATE TABLE IF NOT EXISTS "order" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL,
    raw_payload jsonb NULL -- preserve original payload for auditing
);

CREATE TABLE IF NOT EXISTS order_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES "order" (id) ON DELETE CASCADE,
    sku text NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0),
    weight_kg numeric NOT NULL CHECK (weight_kg >= 0)
);

-- 3. Fulfillment groups (shipments derived from an order)

CREATE TABLE IF NOT EXISTS fulfillment_group (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES "order" (id) ON DELETE CASCADE,
    warehouse_id UUID NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    assigned_route_id UUID NULL
);

CREATE TABLE IF NOT EXISTS fulfillment_group_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fulfillment_group_id UUID NOT NULL REFERENCES fulfillment_group(id) ON DELETE CASCADE,
    order_item_id UUID NOT NULL REFERENCES order_item(id) ON DELETE CASCADE,
    quantity integer NOT NULL CHECK (quantity > 0)
);

-- 4. Warehouses and inventory

CREATE TABLE IF NOT EXISTS warehouse (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    location geography(Point, 4326) NOT NULL,
    operational boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    warehouse_id UUID NOT NULL REFERENCES warehouse (id) ON DELETE CASCADE,
    sku text NOT NULL,
    on_hand integer NOT NULL DEFAULT 0 CHECK (on_hand >= 0),
    reserved integer NOT NULL DEFAULT 0 CHECK (reserved >= 0),
    UNIQUE (warehouse_id, sku)
);

-- 5. Reservations (holds)

CREATE TABLE IF NOT EXISTS reservation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    warehouse_id UUID NOT NULL REFERENCES warehouse (id) ON DELETE CASCADE,
    order_id UUID NOT NULL REFERENCES "order" (id) ON DELETE CASCADE,
    fulfillment_group_id UUID NULL REFERENCES fulfillment_group (id) ON DELETE CASCADE,
    sku text NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0),
    expires_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- 6. Vehicles, drivers, routes

CREATE TABLE IF NOT EXISTS driver (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NULL
);

CREATE TABLE IF NOT EXISTS vehicle (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id text NULL,
    driver_id UUID NULL REFERENCES driver(id),
    max_weight_kg numeric NOT NULL,
    operational boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS route (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id UUID NULL REFERENCES vehicle(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL
);

CREATE TABLE IF NOT EXISTS route_stop (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route_id UUID NOT NULL REFERENCES route(id) ON DELETE CASCADE,
    fulfillment_group_id UUID NOT NULL REFERENCES fulfillment_group(id),
    sequence integer NOT NULL,
    location geography(Point, 4326) NULL
);

-- 7. Telemetry snapshots (periodic history)

CREATE TABLE IF NOT EXISTS telemetry_snapshot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id UUID NOT NULL REFERENCES vehicle(id) ON DELETE CASCADE,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    location geography(Point, 4326) NOT NULL,
    payload jsonb NULL
);

-- Notes and migration guidance

1. Use UUID primary keys and `gen_random_uuid()` from the `pgcrypto` or `pgjwt`/`pgcrypto` extension as appropriate. Ensure migrations include extension creation steps where required.
2. Keep DDL in migration files (Alembic) rather than ad-hoc `CREATE TABLE` runs. The snippets above are reference material for migration authoring.
3. Implement the reservation logic with careful transactional semantics: reserve entries should be created and inventory.reserved incremented in the same transaction to avoid race conditions.
4. Outbox writes MUST occur inside the same transaction as the state change. The application should provide helper utilities to write outbox rows as part of repository/service layer operations.
5. PostGIS types are used for precise spatial storage. Use `geography(Point,4326)` for accurate distance computations when needed.
6. Do not store frequently updated current vehicle locations in Postgres; keep them in Redis for fast reads and persist periodic snapshots for history retention and audit.

Migration checklist

- Add PostGIS extension in an initial migration.
- Add UUID generation extension (e.g., `pgcrypto`) if using `gen_random_uuid()`.
- Create base tables: `warehouse`, `inventory`, `order`, `order_item`, `fulfillment_group`, `fulfillment_group_item`, `vehicle`, `driver`, `route`, `route_stop`, `telemetry_snapshot`, `reservation`, `outbox_event`.
- Add indexes for common lookups (by order_id, fulfillment_group_id, vehicle_id, published flag on outbox).

This file is a living document. Update migration notes and DDL as the domain model stabilizes.
