# Migrations

This directory will host migration tools and scripts (Alembic-based migrations are recommended).

Guidance:

- Add PostGIS extension in the initial migration.
- Add UUID generation extension (e.g., `pgcrypto`) if using `gen_random_uuid()`.
- Create core tables per `backend/app/db/README.md`.
- Use offline-first migration development: author SQL in migration files and verify in a local dev database before applying to other environments.

Do not commit database credentials to the repo. Use environment variables or a secrets manager.
