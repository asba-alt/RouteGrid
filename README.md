# RouteGrid

Real-time urban logistics optimization and delivery management platform — order intake
with inventory reservations, joint vehicle-assignment and route sequencing (OR-Tools
CVRP), simulated GPS telemetry, and disruption recovery with re-optimization.

**Stack:** FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL 16 + PostGIS · Redis · Alembic ·
OR-Tools · React 18 · Vite · TypeScript · Tailwind CSS · Leaflet · Recharts

---

## Status at a glance

| Area | State |
|---|---|
| Backend API | Complete (14 endpoint groups, versioned under `/api/v1`) |
| PostgreSQL/PostGIS | **Verified against a real database** |
| Redis | **Verified against a real Redis** |
| Order intake + reservations | **Verified** (atomic commit + rollback) |
| Route optimization | **Verified** (persisted routes and stops) |
| GPS simulation | **Verified** (persisted telemetry, deterministic) |
| Disruption management | **Verified** (release + preserve completed stops + re-optimize) |
| React dashboard | Complete (8 pages, wired to the API) |
| Tests | Backend **98 passed** · real-DB pipeline **24/24** · frontend **10 passed** |
| Deployment | **Not deployed — prepared only** (needs owner credentials, see below) |

Integration status is documented honestly in
[`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) — mocks are never presented as
real integration verification.

---

## Quick start (local)

Requires PostgreSQL **with PostGIS** and Redis. See
[`docs/COMPLETION_CHECKLIST.md`](docs/COMPLETION_CHECKLIST.md) for the portable local
setup used here (Docker is unusable on this machine: no WSL2/Hyper-V).

> **The virtualenv is at the repository root (`RouteGrid\.venv`), not inside `backend/`.**
> From `backend/` use `..\.venv\Scripts\python.exe`, otherwise you get
> *"The module '.venv' could not be loaded"*.

```bash
cp .env.example .env

# Backend  (venv lives at the repo root)
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head     # review first: --sql
..\.venv\Scripts\python.exe -m scripts.seed_data        # idempotent demo data
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload   # http://localhost:8000/docs

# Frontend (second terminal)
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

First time only, create the venv and install:

```bash
cd C:\Users\Asba\Desktop\Projects\RouteGrid
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e "backend[dev]"
```

Verify everything end to end:

```bash
cd backend
..\.venv\Scripts\python.exe -m scripts.verify_pipeline   # 24/24 → PIPELINE VERIFIED
```

---

## Architecture

```
Browser ── React/Vite dashboard (Leaflet map, Recharts)
   │            │
   │            └── fetch /api/v1/*  (Vite proxy in dev, VITE_API_BASE_URL in prod)
   ▼
FastAPI ── api/routes ── services ── repositories ── SQLAlchemy 2.0 (async)
   │                         │
   │                         ├── optimization/  OR-Tools CVRP
   │                         ├── simulation/    deterministic movement maths
   │                         └── events/outbox  transactional event rows
   ▼
PostgreSQL + PostGIS  (system of record)        Redis (current positions only)
```

Design rules that the code actually follows:

- **One transaction per command.** Order intake commits order + items + reservations +
  `reserved` counters + outbox row together; any failure rolls all of it back.
- **Overselling is prevented by locking, not hoping.** `SELECT … FOR UPDATE` on the
  inventory rows precedes the availability check.
- **Outbox from day one.** Every state change writes its event in the same transaction,
  so there is no dual-write window.
- **The optimizer never overloads a vehicle.** Weight capacity is a hard OR-Tools
  dimension; deliveries that cannot be served are reported as unassigned.
- **Simulation is deterministic.** Position is a pure function of elapsed time — same
  inputs, same output, no randomness.
- **Disruptions preserve completed work.** Only uncompleted stops are released.
- **Failures are honest.** `/health` reports database and Redis separately; errors carry a
  `request_id` and never leak SQL, stack traces or credentials.

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Dependency health (database + Redis) |
| POST/GET | `/api/v1/warehouses` | Create / list warehouses |
| GET/PATCH | `/api/v1/warehouses/{id}` | Detail (with inventory) / update |
| GET | `/api/v1/warehouses/{id}/inventory` | Stock levels |
| PUT | `/api/v1/warehouses/{id}/inventory/{sku}` | Upsert stock |
| POST/GET | `/api/v1/drivers` | Drivers |
| POST/GET | `/api/v1/vehicles` | Vehicles |
| GET/PATCH | `/api/v1/vehicles/{id}` | Vehicle detail / availability |
| POST | `/api/v1/orders/intake` | **Order intake**: validate → lock → reserve → commit |
| POST/GET | `/api/v1/orders` | Create (no reservation) / list, filter by status |
| GET | `/api/v1/orders/{id}` | Order with items and location |
| PATCH | `/api/v1/orders/{id}/status` | Lifecycle transitions (FR-4/FR-6 enforced) |
| POST | `/api/v1/optimization/solve` | **Batch CVRP** solve and persist |
| GET | `/api/v1/routes` · `/api/v1/routes/{id}` | Routes with ordered stops + geometry |
| POST | `/api/v1/simulation/advance` | **GPS simulator** step |
| POST/GET | `/api/v1/disruptions` | Report / list disruptions |
| POST | `/api/v1/disruptions/{id}/resolve` | Resolve, optionally re-optimize |

Interactive docs: `/docs` (Swagger) and `/redoc`.

## Documentation

| Document | Contents |
|---|---|
| [`docs/COMPLETION_CHECKLIST.md`](docs/COMPLETION_CHECKLIST.md) | Verified state, local infra, defect log |
| [`docs/TESTING.md`](docs/TESTING.md) | What each suite proves, mocks vs. real services |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Deployment plan, blockers, exact owner actions |
| [`docs/DEMO.md`](docs/DEMO.md) | 10-minute interview walkthrough |
| [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) | Everything not done or uncertain |
| [`docs/requirements.md`](docs/requirements.md) · [`architecture.md`](docs/architecture.md) | Original specification |
| [`backend/app/db/README.md`](backend/app/db/README.md) | Schema guidance and DDL reference |

## Deployment

Prepared, **not deployed**: [`render.yaml`](render.yaml) (API + Postgres + Redis),
[`backend/Dockerfile`](backend/Dockerfile), [`frontend/vercel.json`](frontend/vercel.json).
Deploying needs the owner to create accounts and supply credentials — see
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). No deployment URL is claimed because none
exists.
