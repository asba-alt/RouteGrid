# Demo walkthrough

A 10-minute script for a technical interview. Every step hits the real API and database.

## 0. Start the stack

```powershell
# PostgreSQL (portable install, see COMPLETION_CHECKLIST.md)
& "C:\Users\Asba\.routegrid-pg\pgsql\bin\pg_ctl.exe" -D "C:\Users\Asba\.routegrid-pg\data" -l "C:\Users\Asba\.routegrid-pg\server.log" -o "-p 5432" start
# Redis
Start-Process "C:\Users\Asba\.routegrid-pg\redis\redis-server.exe" -ArgumentList '--port','6379' -WindowStyle Hidden

# ---- API (terminal 1) ----
# NOTE: the virtualenv lives at the REPO ROOT, not inside backend/.
# From backend/ the path is therefore ..\.venv\Scripts\python.exe
cd C:\Users\Asba\Desktop\Projects\RouteGrid\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload     # http://localhost:8000/docs

# ---- UI (terminal 2) ----
cd C:\Users\Asba\Desktop\Projects\RouteGrid\frontend
npm run dev                                                      # http://localhost:5173
```

Running `.\.venv\Scripts\python.exe` after `cd backend` fails with
*"The module '.venv' could not be loaded"* — there is no `.venv` inside `backend/`.

## 1. Prove the foundation (30s)

Open <http://localhost:8000/health>. Point out it reports **database + redis** separately:
the API degrades honestly instead of pretending both are up.

## 2. Orders and reservations (2 min)

Orders → fill warehouse + SKU + quantity → **Submit order**.
Then open the warehouse's inventory: `reserved` has increased and `available` dropped.
Explain the guarantee: the inventory row is locked with `SELECT … FOR UPDATE`, availability
is measured after the lock, and order + items + reservations + counter + outbox event
commit as one transaction. Submit a quantity larger than stock → **409** with a per-SKU
shortage message and `reserved` unchanged.

## 3. Optimization (2 min)

Optimization → **Run optimization**. Explain this is a CVRP: depots and delivery nodes
form a graph, weight demand is a per-vehicle capacity dimension, arc cost is haversine
distance, and deliveries get a drop penalty so an impossible delivery is reported as
*unassigned* instead of overloading a truck. Uncheck/check local search to discuss the
trade-off (gains are a fraction of a percent on demo-scale data, which is why the default
budget is 2s, not 5s).

## 4. GPS simulation (1 min)

Live Tracking → **Advance simulation** with 360 seconds. 360 real seconds × 60 compression
= 6 simulated hours at 40 km/h. The marker moves along the persisted route, completed
stops tick up, and the progress bar reflects distance travelled over total distance.
State clearly: this is an in-process simulator, not hardware GPS.

## 5. Disruption (2 min)

Disruptions → choose a route → **Report disruption** (vehicle breakdown).
Show the result: the route is cancelled, *uncompleted* deliveries return to
`PENDING_ALLOCATION`, and **completed** stops are preserved. Then
**Resolve + re-optimize** → new routes are generated for the released work.

## 6. Failure modes (1.5 min)

- Stop Redis (`taskkill /IM redis-server.exe /F`) → `/health` shows `redis: error`,
  the UI badge goes amber, and everything except position caching still works.
- Submit an invalid order (quantity 0) → **422** with field-level detail.
- Request a missing order id → **404** in the same envelope, carrying a `request_id`
  you can grep in the JSON logs.

## Talking points

- Why a modular monolith: cross-cutting transactional guarantees (order + inventory +
  outbox) are trivial in one process and painful across services.
- Why outbox: no dual-write between state and events.
- Why the frontend shows `request_id`: an operator can quote it to support.
- What is deliberately not built: JWT/RBAC, Kafka consumer, warehouse-selection
  heuristic, Playwright E2E, real deployment.
