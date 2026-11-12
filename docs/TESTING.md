# Testing

## What runs, and what it proves

| Suite | Command | Count | Proves |
|---|---|---|---|
| Backend unit + integration | `cd backend && python -m pytest -q` | **98 passed** | Domain rules, solver, simulator maths, API wiring, error handling |
| Real-database pipeline | `cd backend && python -m scripts.verify_pipeline` | **24/24 PASS** | Migrations, PostGIS, `FOR UPDATE` locking, atomicity, persistence, disruption recovery |
| Frontend unit | `cd frontend && npm test` | **10 passed** | Error envelope mapping, retry policy, UI state primitives |
| TypeScript | `cd frontend && npm run typecheck` | clean | Type safety |
| Production build | `cd frontend && npm run build` | success | Buildable artefact |

**Mocks vs. real services.** `pytest` uses mocked repositories/sessions for the service
layer. `scripts/verify_pipeline.py` is the only suite that touches real PostgreSQL,
PostGIS and Redis, and it proves the claims mocks cannot: geography round-tripping, row
locking, transaction commit/rollback and outbox writes.

## Prerequisites for the real-database suite

PostgreSQL 16 + PostGIS 3.6 and Redis must be running and reachable at the URLs in
`.env` (see `docs/COMPLETION_CHECKLIST.md` for the portable local layout).

```powershell
python -m alembic upgrade head
python -m scripts.seed_data          # idempotent; safe to re-run
python -m scripts.verify_pipeline    # exit 0 == verified
```

`verify_pipeline` exits `2` when the database is unreachable and claims nothing.

## Negative and resilience behaviour covered

| Scenario | Behaviour | Where |
|---|---|---|
| Insufficient stock | 409, `reserved` unchanged, no orphan reservations | `verify_pipeline` |
| Concurrent reservation | Second transaction blocks on `SELECT … FOR UPDATE` | `verify_pipeline` |
| Database down | `/health` → 503 `{database: error}`; API returns 503 envelope | `tests/integration/test_health.py` |
| Redis down | Degraded health, cache bypassed, requests still served | unit + `/health` |
| Invalid route for simulation | 404 unknown, 409 already-completed | `tests/unit/test_simulation_service.py` |
| Missing coordinates | Stops skipped and reported as remaining; route never crashes | movement/service tests |
| No vehicles / infeasible CVRP | `solved=false`, everything reported unassigned | `test_optimization_cvrp.py` |
| Over-capacity delivery | Never overloads a vehicle; reported unassigned | `test_optimization_cvrp.py` |
| Failed disruption recovery | Disruption marked `UNRESOLVED`, completed stops preserved | `disruption_service` |
| Duplicate UI submission | Submit buttons disable while in flight | `pages/*.tsx` |
| Malformed payload | 422 with field-level detail, no body echo | `app/core/errors.py` |

## Not yet automated

- Playwright end-to-end journey (browser) — not implemented.
- A committed `pytest` module for real-DB integration; the equivalent checks live in
  `scripts/verify_pipeline.py` instead.
