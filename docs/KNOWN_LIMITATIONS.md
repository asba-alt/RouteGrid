# Known limitations

Honest, current list. Items marked **verified** were exercised against real services.

## Not implemented

1. **Deployment.** No public URL exists. Requires owner accounts/credentials — see
   `docs/DEPLOYMENT.md`. Everything else is prepared.
2. **Authentication/authorisation.** `get_current_user` is a deliberate seam returning a
   fixed dev user (NFR-4). No JWT, no RBAC, no per-role permissions.
3. **Rate limiting.** Not implemented.
4. **Warehouse-selection heuristic** (FR-15/FR-16). Order intake takes an explicit
   `warehouse_id`; the weighted distance/workload/time score is not built.
5. **Reservation expiry/release** (OQ-2 unresolved). `expires_at` is written as `NULL`
   and nothing releases holds automatically.
6. **Intake idempotency.** No `Idempotency-Key`; a duplicated POST creates a second order.
7. **Outbox consumer.** Rows are written transactionally; no poller/Kafka publication yet.
8. **Background worker.** Not deployed; batch optimization is triggered by API call.
9. **Playwright E2E.** Not implemented; the journey is covered by unit + real-DB suites.
10. **Order status derivation from fulfillment groups (FR-3).** v1 materialises one group
    per order, so order-level status is set directly.
11. **Vehicle double-booking.** A vehicle holding an active route can be assigned a second
    one in a later batch; there is no active-route exclusion.
12. **Frontend coverage.** Eight pages exist and are wired to the API, but only the shared
    primitives and API client have automated tests.

## Interpretation decisions worth confirming

13. **`order_item.weight_kg` is treated as per-unit weight** (demand = quantity × weight).
    The specification does not say. Encoded in one function
    (`optimization_service.item_weight_g`) so it is a one-line change.
14. **Route status vocabulary** (`PLANNED` → `IN_PROGRESS` → `COMPLETED`/`CANCELLED`,
    stops `PENDING` → `COMPLETED`/`RELEASED`) is ours; the requirements define order
    states but not route states.
15. **Simulator skips intermediate order states.** A group goes `ALLOCATED` →
    `OUT_FOR_DELIVERY` → `DELIVERED`; `PICKING`/`READY_FOR_DISPATCH` belong to warehouse
    operations and are not modelled.

## Environment limitations on this machine

16. **Docker cannot run** (no WSL2 distro, no Hyper-V). Docker Desktop is installed but
    the engine will not start. Do not retry it.
17. **Redis is 5.0.14**, the only maintained Windows build. The client pins RESP2 so
    managed Redis 7.x works unchanged.
18. **Local PostgreSQL is a portable 16.15 + PostGIS 3.6.2** tree under
    `C:\Users\Asba\.routegrid-pg` with `trust` auth on loopback, so the password in the
    URL is accepted but not checked. It is not a substitute for a managed production DB.
19. **`verify_pipeline.py` mutates data** (it creates a warehouse, submits orders, and a
    batch solve assigns every pending order). It is intended for a disposable dev
    database. Repeated runs leave `Verify Hub …` warehouses behind.
