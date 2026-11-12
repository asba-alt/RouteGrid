# Deployment

## Status: prepared, **not deployed**

No public deployment exists. Deploying requires an account and credentials that only
the repository owner can create; nothing was fabricated and no service was subscribed
to. Everything that can be prepared without an account is committed:

| Artifact | Purpose |
|---|---|
| `backend/Dockerfile` | Production image (non-root, `/health` HEALTHCHECK) |
| `backend/.dockerignore` | Keeps `.env`, tests and caches out of the image |
| `backend/.env.production.example` | Required production variables |
| `render.yaml` | Render blueprint: API + Postgres + Redis |
| `frontend/vercel.json` | SPA rewrites + immutable asset caching |
| `frontend/.env.example` | `VITE_API_BASE_URL` |

## Target architecture

| Layer | Service | Notes |
|---|---|---|
| Frontend | Vercel (static) | `npm run build` → `dist` |
| Backend | Render (Docker web service) | `backend/Dockerfile`, health check `/health` |
| Database | Render Postgres 16 **or** Neon | Must support PostGIS |
| Redis | Render Key Value **or** Upstash | RESP2 compatible; any Redis 5+ works |
| Maps | OpenStreetMap tiles | No API key |

## Exact steps the owner must take

1. **Create accounts** — Vercel and Render (or Neon). Free tiers change; verify current
   pricing before accepting anything paid.
2. **Create a PostGIS database.** Neon: `CREATE EXTENSION postgis;` works on the free tier.
   Render Postgres 16 also ships PostGIS. Note both connection URLs (async + sync).
3. **Deploy the API.** Render → New → Blueprint → this repo (`render.yaml`). Set the
   `sync: false` secrets:
   ```
   DATABASE_URL=postgresql+asyncpg://…?ssl=require
   DATABASE_URL_SYNC=postgresql+psycopg2://…?sslmode=require
   REDIS_URL=rediss://…
   CORS_ORIGINS=https://<your-vercel-app>.vercel.app
   ```
4. **Apply migrations once**, from a shell with the production `DATABASE_URL_SYNC`:
   ```
   cd backend && python -m alembic upgrade head
   python -m scripts.seed_data      # optional demo data
   ```
   Review the generated SQL first: `python -m alembic upgrade head --sql`.
5. **Deploy the frontend.** Vercel → import repo → root `frontend` → set
   `VITE_API_BASE_URL=https://<your-api>.onrender.com` → deploy.
6. **Re-set `CORS_ORIGINS`** on the API to the final Vercel URL (an empty value fails
   closed, so this is a hard requirement, not a nicety).
7. **Verify:**
   ```
   curl -s https://<api>.onrender.com/health
   #   {"status":"ok","database":"connected","redis":"connected"}
   curl -s -o /dev/null -w "%{http_code}\n" https://<app>.vercel.app/
   ```

## Production configuration notes

- `APP_ENV=production` and `DEBUG=false` disable debug logging.
- **CORS fails closed.** `CORS_ORIGINS` empty in production returns no allowed origins
  rather than a wildcard.
- The container binds `$PORT` and trusts `X-Forwarded-*` from the platform proxy.
- Secrets live only in the platform's env settings; `.env*` is gitignored and
  `.dockerignore`d.
- Render free web services sleep when idle — the first request after idle is slow. That
  is a platform characteristic, not an application timeout.
- No background worker is deployed: outbox rows are written transactionally but nothing
  consumes them yet.

## What is verified locally vs. what remains unverified

| Claim | Verified? |
|---|---|
| Dockerfile builds | **Not verified** — Docker cannot run on this machine (no WSL2/Hyper-V) |
| `render.yaml` schema | Not verified against a live Render account |
| Migrations on a real PostGIS database | **Verified locally** (portable PostgreSQL 16.15 + PostGIS 3.6.2) |
| Production PostGIS provider | Not verified — requires an account |
| Public URLs | None exist |
