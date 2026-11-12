# RouteGrid — Completion Checklist & Handoff

Updated after: backend completion, hardening, disruption management, React dashboard.

## Local infrastructure (portable — Docker is unusable here)

**Docker Desktop has been uninstalled from this machine** (`docker` CLI absent, no
`Docker Desktop.exe`), and it could not run anyway: no WSL2 distro and no Hyper-V. Do not
retry it, and do not expect `docker compose up -d` to work. A portable stack lives in
`C:\Users\Asba\.routegrid-pg` (outside the repo):

| Component | Path | Port |
|---|---|---|
| PostgreSQL 16.15 + PostGIS 3.6.2 | `.routegrid-pg\pgsql`, data `.routegrid-pg\data` | 5432 |
| Redis 5.0.14.1 (Windows build) | `.routegrid-pg\redis` | 6379 |

Loopback `trust` auth; credentials in `.env` are accepted but not checked.

```powershell
& "C:\Users\Asba\.routegrid-pg\pgsql\bin\pg_ctl.exe" -D "C:\Users\Asba\.routegrid-pg\data" -l "C:\Users\Asba\.routegrid-pg\server.log" -o "-p 5432" start
Start-Process "C:\Users\Asba\.routegrid-pg\redis\redis-server.exe" -ArgumentList '--port','6379' -WindowStyle Hidden
```

## Running the application

**The virtualenv is at the repository root — `RouteGrid\.venv` — NOT inside `backend/`.**
Running `.\.venv\Scripts\python.exe` from `backend/` fails with
*"The module '.venv' could not be loaded"*.

```powershell
# ---- API (terminal 1) ----
cd C:\Users\Asba\Desktop\Projects\RouteGrid\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
#  or, with the venv activated:
#    C:\Users\Asba\Desktop\Projects\RouteGrid\.venv\Scripts\Activate.ps1
#    cd backend; python -m uvicorn app.main:app --reload

# ---- UI (terminal 2) ----
cd C:\Users\Asba\Desktop\Projects\RouteGrid\frontend
npm run dev
```

Migrations/seed only when needed (they are already at head `0002_disruption`):

```powershell
cd C:\Users\Asba\Desktop\Projects\RouteGrid\backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m scripts.seed_data          # idempotent
..\.venv\Scripts\python.exe -m scripts.verify_pipeline    # 24/24
```

Endpoints once running: API <http://127.0.0.1:8000/docs> ·
UI <http://127.0.0.1:5173> · health <http://127.0.0.1:8000/health>

## Known environment blocker: psycopg2 is blocked by OS policy

`import psycopg2` fails with:

```
ImportError: DLL load failed while importing _psycopg: An Application Control policy has blocked this file.
```

This breaks **Alembic** and **`scripts/seed_data.py`** (both use the sync driver). It does
**not** affect the API, which uses asyncpg, and it does not affect `psql`.

Workarounds used here:
- Migrations were applied with `psql` and `alembic_version` was updated manually
  (migration `0003_order_reference`: add `customer_name`, `reference`, index).
- Data backfills were run through the async engine
  (`create_async_engine` + `async_session_factory`).

Reinstalling `psycopg2-binary` produces the same blocked DLL, so an allowlist entry in the
Application Control policy is the real fix. If you need `alembic upgrade head` to work,
either allowlist that DLL or switch Alembic's `env.py` to an async engine.

## Verified against real services

`python -m scripts.verify_pipeline` → **24/24 PASS**, exit 0.

Schema (18 tables incl. `disruption`, PostGIS 3.6, `timestamptz`, `geography`) ·
`FOR UPDATE` blocking a second session · atomic intake (order/items/reservations/counter/
outbox) · 409 with no partial hold · optimizer persistence (routes, ordered stops,
`ALLOCATED`, `RoutePlanned` outbox) · simulator persistence (telemetry snapshots) ·
disruption (route cancelled, 5 released, **7 completed stops preserved**, orders back to
`PENDING_ALLOCATION`, re-optimized into 3 routes) · Redis reachable.

## Test status

| Suite | Result |
|---|---|
| Backend `pytest` | **98 passed** |
| Real-DB pipeline | **24/24 PASS** |
| Frontend `vitest` | **10 passed** |
| TypeScript `tsc --noEmit` | clean |
| `npm run build` | success (740 kB JS / 216 kB gzip) |
| Frontend ↔ backend via Vite proxy | **verified** (`/health` → database+redis connected) |

## Defects found only by real-database verification (fixed)

1. `wkb_to_geo_point` crashed on the string form of a geography value
   (`expire_on_commit=False` keeps the WKT literal). Now accepts `WKBElement`, hex WKB and
   EWKT/WKT. Regression tests added. Mocks could not have caught this.
2. redis-py 8 defaults to RESP3 (`HELLO 3`) which Redis 5.x rejects → pinned `protocol=2`.
3. `verify_pipeline.py` imported `async_session_factory` by value, so it stayed `None`.
4. Local-search default of 5s burned the full budget for ≤0.7 % gain → configurable
   `OPTIMIZER_TIME_LIMIT_SECONDS` (default 2). Local search itself verified functional
   (matches OR-Tools directly).
5. `SPEED_FACTOR_KMH` was dead config → now drives the ETA returned by the optimizer.

## Definition-of-done tracker

| Item | Status |
|---|---|
| Backend implementation | ✅ complete |
| PostgreSQL/PostGIS integration | ✅ verified |
| Redis integration | ✅ verified |
| Order intake + inventory transactions | ✅ verified |
| Route optimization | ✅ verified |
| GPS simulation | ✅ verified |
| Disruption management | ✅ verified |
| React frontend | ✅ 8 pages, API-wired |
| Frontend/backend integration | ✅ verified via proxy |
| Interactive map | ✅ built (OSM tiles, list fallback on tile failure) |
| Error handling / fallbacks | ✅ centralised handlers, request ids, degradation |
| Security controls | ⚠️ CORS fail-closed, parameterised ORM, non-root container; **no auth/rate limiting** |
| Unit tests | ✅ 98 backend + 10 frontend |
| Integration tests | ✅ 24/24 real DB |
| API tests | ⚠️ partial (error envelope, validation, 404/409/422, health) |
| Frontend tests | ⚠️ primitives + API client only |
| End-to-end tests | ❌ Playwright not implemented |
| Negative/resilience tests | ✅ DB down, Redis down, bad payloads, no vehicles, over-capacity, missing coords |
| Production build | ✅ frontend builds; ⚠️ backend Dockerfile **not built** (no container runtime) |
| Documentation | ✅ README + docs/* |
| Frontend deployed | ❌ **blocked** — owner credentials |
| Backend deployed | ❌ **blocked** — owner credentials |
| Deployment smoke tests | ❌ blocked by the above |

## Exact next actions for the owner

1. Create Vercel + Render (or Neon) accounts and a PostGIS database.
2. Follow `docs/DEPLOYMENT.md` steps 1–7; supply the `sync: false` secrets.
3. Run `python -m alembic upgrade head` against the production `DATABASE_URL_SYNC`.
4. Set `CORS_ORIGINS` to the final Vercel URL — it fails closed when empty.
5. Verify `/health` returns `{"status":"ok", ...}` before declaring deployment done.

## Optional follow-ups (not blocking)

- `Idempotency-Key` support for order intake.
- Reservation expiry/release policy (OQ-2 undecided).
- Active-route exclusion so a vehicle cannot be double-booked across batches.
- Playwright journey; Docker image build verification on a machine with a container runtime.
