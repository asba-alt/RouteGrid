# RouteGrid Requirements

## 1. Purpose and scope

RouteGrid is a planning-stage operational platform for managing urban delivery execution from order intake through final delivery completion. The system coordinates warehouses, inventory, vehicles, drivers, and route execution for a real city environment represented as a synthetic operational dataset overlayed on a real OpenStreetMap bounding box. The product is intended for dispatch and operations staff who need to understand current demand, allocation status, vehicle load, and disruption response in near real time.

This system is not a generic CRUD application, not a showcase for microservices for their own sake, and not a black-box optimization platform with hidden logic. It is an operational management system whose v1 design is deliberately modest: a modular monolith using FastAPI, PostgreSQL/PostGIS, and React, with a simple in-process GPS simulator and Redis cache for current vehicle state. The architecture is intentionally constrained to keep the implementation explainable and defensible during early development.

The core operational flow in v1 is:
- customer order intake,
- warehouse selection,
- inventory reservation,
- joint vehicle assignment and route optimization,
- simulated vehicle telemetry,
- tracking and disruption response,
- delivery completion and status updates.

The intended user roles are dispatcher/operator users who monitor and intervene in live delivery operations. These users are expected to review pending allocations, fulfillment progress, disruption scenarios, and dispatch exceptions. They are not expected to be warehouse clerks, fleet engineers, or end customers in v1.

The system is designed around real operational disruption handling, especially vehicle breakdowns and warehouse outages, which are treated as first-class scenarios. RouteGrid must detect affected delivery groups, pool them into a recalculation context, and trigger a coordinated rescheduling and reoptimization flow rather than isolated one-off fixes.

The v1 scope covers a complete, bounded demo of this workflow in a controlled synthetic environment. It explicitly excludes broader enterprise concerns such as full RBAC enforcement, live hardware GPS integration, road-network-based routing, time-windowed delivery constraints, and production-scale platform concerns.

## 2. Functional requirements

### 2.1 Orders

FR-1: The system shall maintain a distinct order record for each customer order, including customer identity, order creation time, requested fulfillment window if present, and overall order status.

FR-2: The system shall support partial order fulfillment such that a single order may be split into multiple fulfillment groups, each tied to one warehouse and a subset of items from the original order.

FR-3: The system shall derive the overall order status from the statuses of its fulfillment groups, such that an order is only marked as `DELIVERED` when all of its fulfillment groups are delivered and `PARTIALLY_SHIPPED` is available while some groups remain unshipped or in progress.

FR-4: The system shall reject an order-cancellation request if any fulfillment group for the order has already reached `OUT_FOR_DELIVERY` or a later state unless the cancellation policy explicitly allows a later change by operations.

FR-5: The system shall allow an order to remain in a `PENDING_ALLOCATION` state until the next batch optimization run assigns vehicles and routes to its associated fulfillment groups.

FR-6: The system shall expose a visible order lifecycle state model that includes at least: `PENDING_ALLOCATION`, `ALLOCATED`, `PICKING`, `READY_FOR_DISPATCH`, `OUT_FOR_DELIVERY`, `DELIVERED`, `PARTIALLY_SHIPPED`, `CANCELLED`, and `FAILED` or equivalent operational states defined by the domain model.

FR-7: The system shall support a mechanism for associating each fulfillment group to a warehouse, one or more ordered items, and a delivery assignment so that order-level tracking can be decomposed into trackable shipment units.

### 2.2 Warehouses & Inventory

FR-8: The system shall maintain warehouse records for 4–6 operational warehouses in the demo environment, each with a location, operational status, and associated inventory profile.

FR-9: The system shall maintain inventory records by warehouse and SKU, including on-hand quantity and reservation/hold quantity required to prevent overselling under concurrent order processing.

FR-10: The system shall allow a warehouse to be marked as operational or non-operational so that orders cannot be assigned to an unavailable warehouse.

FR-11: The system shall support inventory reservation such that a fulfillment group reserves the relevant inventory at its assigned warehouse before it is considered ready for allocation.

FR-12: The system shall release a reservation when an order is cancelled, a fulfillment group is rejected, or a reservation times out under the configured timeout policy.

FR-13: The system shall permit a single order to be fulfilled by multiple warehouses when no single warehouse can satisfy the full order or when a warehouse-selection heuristic indicates a split is operationally preferable.

FR-14: The system shall reject a warehouse assignment if the required items are not available at that warehouse after accounting for existing reservations and on-hand stock.

FR-15: The system shall calculate warehouse suitability using a hand-rolled heuristic that applies hard constraints first, then a weighted score over normalized distance, current workload, and estimated delivery time. The initial weights shall be explicit configuration values and shall be documented as a starting heuristic, not a validated optimum.

FR-16: The system shall use a warehouse-selection score that is evaluated before routing optimization; the routing engine shall not own that decision in v1.

### 2.3 Fleet & Drivers

FR-17: The system shall maintain a fleet of 20–30 vehicles in the demo configuration, each assigned to exactly one driver per shift, with no shift-scheduling engine in v1.

FR-18: The system shall maintain vehicle records including vehicle ID, current depot or warehouse association, capacity, operational status, and current route assignment state.

FR-19: The system shall represent vehicle capacity using a single weight dimension measured in kilograms for v1; volume-based capacity is out of scope for v1.

FR-20: The system shall reject an assignment that exceeds the vehicle's available weight capacity after accounting for assigned fulfillment groups.

FR-21: The system shall maintain a driver record for each vehicle and shall treat driver assignment as fixed for the active shift in v1; no driver scheduling or shift rotation logic is required.

FR-22: The system shall track vehicle operational status so that an unavailable or broken-down vehicle is excluded from the next batch optimization run.

### 2.4 Route Optimization & Assignment

FR-23: The system shall treat vehicle assignment and route sequencing as a single joint optimization problem solved over a batch of pending orders and available vehicles using OR-Tools or an equivalent constrained routing solver.

FR-24: The system shall not assign a new order to a vehicle immediately on order arrival; instead, the order shall enter a `PENDING_ALLOCATION` state and wait for the next batch solve.

FR-25: The system shall trigger a batch optimization solve when either 10 new pending orders have accumulated or 15 seconds have elapsed since the previous solve, whichever occurs first. This value shall serve as the initial batching policy placeholder and may be revised later with explicit sign-off.

FR-26: The system shall solve a CVRP-style routing problem without time windows in v1; delivery time-window constraints are explicitly deferred to v2.

FR-27: The system shall assign each fulfillment group to a vehicle and determine stop order within the same optimization batch rather than using a separate order-by-order vehicle selection step.

FR-28: The system shall treat a route as the ordered set of stops for an assigned vehicle during a delivery cycle and shall persist enough route data to reconstruct the path and sequence used by the vehicle.

FR-29: The system shall approximate travel time in v1 as straight-line distance multiplied by a configurable speed factor and shall label this as an approximation, not a road-network-accurate result.

FR-30: The system shall not use real road-network routing in v1; real routing via OSRM or a similar engine is explicitly deferred to v2.

FR-31: The system shall maintain a resolved route for each active vehicle assignment and shall allow the route to be updated as re-optimization occurs after disruption events.

### 2.5 Real-Time Tracking

FR-32: The system shall simulate vehicle telemetry using an in-process simulator rather than interfacing with real GPS hardware in v1.

FR-33: The system shall interpolate each vehicle's position along its assigned route in simulated time, where real-world minutes or hours are compressed into seconds for demo purposes.

FR-34: The system shall cache the current vehicle position in Redis for fast read access, while periodically persisting snapshots of vehicle history to PostgreSQL for audit and replay purposes.

FR-35: The system shall clearly present telemetry as simulated data produced by an in-process simulator and not as measurements from operational hardware devices.

FR-36: The system shall allow a dispatcher to view the current status of each active vehicle, including its current simulated position, assigned route, and fulfillment progress.

FR-37: The system shall update the state of fulfillment groups and orders as vehicles move along their assigned routes and complete stops in the simulated timeline.

### 2.6 Failure Handling

FR-38: The system shall support the operational failure scenario in which a vehicle becomes unavailable due to a breakdown or equivalent disruption.

FR-39: When a vehicle breaks down, the system shall re-collect the orphaned stops from the affected vehicle and place them back into the set of pending or reassignable fulfillment groups for a new optimization pass.

FR-40: The system shall trigger a re-solve of a sub-batch of affected assignments among remaining available vehicles following a vehicle breakdown, instead of reassigning each stop individually in a local greedy pass.

FR-41: The system shall treat the visible recalculation delay that accompanies a breakdown response as expected system behavior in v1, not as a defect or hidden recovery shortcut.

FR-42: The system shall support warehouse outage handling such that affected fulfillment groups are withheld from allocation until the warehouse returns to operational status or they are reassigned after an operational decision.

FR-43: The system shall allow failed or disrupted fulfillment groups to be reintroduced into the optimization queue after a disruption is resolved or an alternate warehouse/vehicle plan is created.

FR-44: The system shall maintain an auditable sequence of route and assignment changes so that dispatch operators can review what was re-optimized and why.

### 2.7 Events

FR-45: The system shall use an outbox pattern from day one, writing each meaningful state change to a Postgres events/outbox table in the same database transaction as the state change itself.

FR-46: The system shall store outbox event rows containing at least the event type, aggregate identifier, payload, and publication status so that downstream consumers can process the event later.

FR-47: Before Kafka or any asynchronous broker is introduced, the system shall not depend on a message bus for core state propagation; the outbox table may be inspected by debugging or audit views only.

FR-48: When Kafka is introduced later, the system shall publish unpublished outbox rows via a poller without requiring changes to the producer code paths that already wrote the events.

FR-49: The system shall treat the outbox pattern as a deliberate architecture choice to avoid a dual-write problem between application state and event streams.

### 2.8 Reporting / Dashboard

FR-50: The system shall provide a dashboard view for dispatch operators showing current orders, their allocation status, active vehicle assignments, and fulfillment progress by warehouse and route.

FR-51: The system shall provide a summary view of operational disruption status, including vehicles marked unavailable and warehouses marked non-operational.

FR-52: The system shall expose order and fulfillment status information in a way that lets an operator identify whether an order is partially fulfilled, fully delivered, or awaiting reallocation.

FR-53: The system shall provide a view of vehicle telemetry and route assignment state for all currently active vehicles in the simulated demo environment.

FR-54: The system shall make dashboard content operationally interpretable without requiring historical benchmarking or fabricated performance claims.

## 3. Non-functional requirements

NFR-1: The system shall support idempotent event handling at the consumer boundary so that duplicate or replayed events do not create duplicate state changes.

NFR-2: The system shall not claim or fabricate performance, throughput, or optimization-quality metrics that have not been measured under the project’s actual workload conditions.

NFR-3: The system shall store configuration in environment variables or equivalent external configuration for sensitive and environment-specific settings, including database connection values, Redis host configuration, and operational tuning parameters.

NFR-4: The system shall provide a `get_current_user`-style dependency/seam from day one, even though full auth enforcement is deferred. The initial implementation shall return a hardcoded fake user so endpoint signatures remain stable for later real JWT/RBAC integration.

NFR-5: The system shall document that the GPS telemetry is simulated and compressed in time; it must not be represented as real hardware integration or wall-clock field data.

NFR-6: The system shall isolate the v1 operational model from later event-driven and analytics enhancements so that Kafka, Redis stream processing, and advanced optimization services can be introduced without requiring a full rewrite of the core domain model.

NFR-7: The system shall maintain separate operational responsibilities for warehouse selection, route optimization, and telemetry simulation so that future enhancements can replace one component without restructuring the entire platform.

NFR-8: The system shall ensure that the demo environment can be run with the defined v1 scales: 4–6 warehouses, 20–30 vehicles, 30–50 SKUs, 100–300 orders per day steady state, and 10–15 concurrent in-transit vehicles.

NFR-9: The system shall treat load testing with Locust or equivalent synthetic traffic as a separate, later concern and shall not conflate it with the steady-state demo-scale requirements of v1.

NFR-10: The system shall keep the v1 implementation explainable and modular enough for a student developer to defend in design review without relying on hidden infrastructure magic or unbounded complexity.

## 4. Explicit v1 scope boundary

### In scope for v1
- Real-world city dataset represented as a real OSM bounding box with synthetic warehouses, customers, and orders.
- Synthetic, demo-scale operational data for 4–6 warehouses, 20–30 vehicles, 30–50 SKUs, and 100–300 orders per day steady state.
- Partial order fulfillment via fulfillment groups under a single order.
- Inventory reservation/hold logic to prevent overselling.
- Warehouse selection based on hard constraints followed by a weighted heuristic over distance, workload, and estimated delivery time.
- Joint vehicle assignment and route optimization using OR-Tools over a batch of pending orders and vehicles.
- Batch solve trigger policy with a concrete placeholder: 10 pending orders or 15 seconds since the last solve, whichever occurs first.
- Simulated, in-process vehicle GPS telemetry with compressed time and Redis caching.
- Periodic telemetry snapshot persistence to PostgreSQL for history.
- Operational handling of warehouse outages and vehicle breakdowns via re-solve of a disrupted sub-batch.
- Outbox pattern from day one with Postgres transactional event storage.
- Auth seam via a `get_current_user`-style dependency returning a fake user for later JWT/RBAC replacement.

### Explicitly deferred to v2+
- Real road-network-aware routing via OSRM or equivalent routing engine.
- Real GPS or live hardware telemetry integration.
- Time-windowed delivery constraints (VRPTW) and delivery time-window scheduling.
- Volume-based vehicle capacity.
- Kafka as an active transport for event publication and consumption.
- Full JWT/RBAC enforcement with user roles, permissions, and secure session handling.
- ML-based ETA prediction and advanced learning-based optimization.
- Cloud-native deployment, autoscaling, and production infrastructure concerns.
- Advanced load and stress testing beyond the separate, later Locust-based performance investigation.
- Real-time streaming from connected or external devices beyond the bundled simulator.

## 5. Open questions / assumptions requiring sign-off

OQ-1: The batch solve trigger policy is intentionally set to a placeholder value of 10 pending orders or 15 seconds, whichever occurs first, but the product owner must confirm whether this should be tuned tighter for faster dispatch responsiveness or looser for lower compute churn.
- Option A: Keep the default as 10/15 and use this as the initial demo policy.
- Option B: Favor time-based dispatching, such as 15 seconds maximum latency, even with fewer orders.
- Option C: Favor count-based dispatching, such as 5 or 10 orders, to reduce volatility in the optimization queue.

OQ-2: The domain model still needs a precise definition of which order and fulfillment-group states are considered terminal for operational reporting and cancellation policies.
- Option A: Treat `DELIVERED`, `CANCELLED`, and `FAILED` as terminal states only.
- Option B: Treat `PARTIALLY_SHIPPED` as a terminal state at the order level only if all its fulfillment groups are resolved.
- Option C: Use a richer state machine with explicit `REASSIGNED`, `RETRY_PENDING`, and `ABANDONED` states after disruption.

OQ-3: The exact rules for reservation timeout and release behavior are not yet specified for the v1 product.
- Option A: Expire reservations after a fixed timeout from creation and automatically release them.
- Option B: Require operator intervention to release reservations on timeout or cancellation.
- Option C: Use a hybrid model where timeout is automatic for pending allocations and manual release is required after dispatch begins.

OQ-4: The derived order-level status rules need sign-off for edge cases involving mixed success and failure across multiple warehouses.
- Option A: Mark the order as `PARTIALLY_SHIPPED` when any fulfillment group is active and not all are delivered.
- Option B: Treat partial fulfillment as a dashboard-only status and keep order status simple until final delivery or cancellation.
- Option C: Introduce a separate operational state for `PARTIALLY_FAILED` or `REBALANCING` when a subset of groups is re-optimized.

OQ-5: The initial warehouse score weights for distance, workload, and estimated delivery time are intentionally arbitrary placeholders; they should be explicitly reviewed by stakeholders before they are treated as operational policy.
- Option A: Use a fixed starting configuration and keep the score as a documented heuristic.
- Option B: Allow a lightweight admin setting to tune weights in configuration without changing code.
- Option C: Keep weights hardcoded until the product owner approves a tuning exercise.

## 6. Glossary

- Order: A customer request that may consist of multiple items and may be fulfilled from one or more warehouses.
- Fulfillment Group: A shipment unit under an order, tied to one warehouse, a subset of order items, and its own delivery assignment and route.
- Reservation: An inventory hold placed against a warehouse/supplier stock count to prevent overselling while an order is pending allocation or in transit.
- Warehouse Selection Heuristic: The pre-routing scoring process that chooses a warehouse candidate based on hard constraints and weighted normalized distance, workload, and estimated delivery time.
- Batch Solve: The optimization pass that jointly determines vehicle assignment and route sequencing for a group of pending orders and available vehicles.
- Route: The ordered sequence of stops assigned to a vehicle during a delivery cycle.
- Outbox Event: A transactional event record written to a Postgres outbox table in the same database transaction as the business state change.
- Simulated Telemetry: Vehicle position data generated by an in-process simulator that compresses real-world time into a demo-friendly scale and does not represent real hardware integration.
- CVRP: Capacitated vehicle routing problem; this is the routing model used in v1 without time windows.
- VRPTW: Vehicle routing problem with time windows; explicitly deferred to v2.
- PENDING_ALLOCATION: The state an order or fulfillment group occupies while it waits for the next batch optimization cycle.
- Re-solve: A new optimization run triggered after a disruption such as a breakdown or warehouse outage, used to recalculate assignments over the affected sub-batch.

This requirements document defines the v1 scope and constraints for RouteGrid. It intentionally excludes unbounded feature expansion and keeps the system aligned with the project’s modular-monolith-first strategy and the explicit deferrals for v2+ capabilities.
