# RAG Learning Platform

Phase 1 scaffolds a reviewable foundation for a document-grounded RAG application:

- `web/`: Next.js dashboard with Supabase-authenticated login, file upload UI, and document/job views.
- `api/`: FastAPI service with authenticated upload, workspace-aware document listing, and job status APIs.
- `worker/`: background worker skeleton reserved for Phase 2 ingestion.
- `infra/`: local infrastructure files for PostgreSQL with `pgvector` and Redis.
- `docs/`: review notes and architecture handoff material.

## Phase 1 scope

- Authenticated dashboard with Supabase SSR middleware.
- `POST /v1/documents/upload`
- `GET /v1/documents`
- `GET /v1/jobs/{id}`
- Workspace-aware document/job lifecycle persisted in PostgreSQL.
- Storage abstraction with `local` default and optional `supabase` object upload support.
- Local PostgreSQL is published on host port `15432` to avoid conflicts with existing Postgres installs.

## Local prerequisites

- Node.js 20+
- Python 3.12+ (or any compatible interpreter path)
- Docker Desktop
- A Supabase project for auth, plus optionally storage if `STORAGE_BACKEND=supabase`

## Environment

Copy these files and fill them in:

- `web/.env.example` -> `web/.env.local`
- `api/.env.example` -> `api/.env`
- `worker/.env.example` -> `worker/.env`

## Infrastructure

Start PostgreSQL and Redis:

```powershell
docker compose -f infra/docker-compose.yml up -d
```

PostgreSQL will be reachable on `127.0.0.1:15432`.

## Web

Install and run from the root:

```powershell
npm install
npm run web:dev
```

## API

Create a Python environment, install dependencies, and run:

```powershell
C:\Users\jvb\AppData\Local\Python\bin\python.exe -m venv .venv
.venv\Scripts\python.exe -m pip install -e .\api
.venv\Scripts\python.exe -m uvicorn api.app.main:app --reload --app-dir .
```

## Tests

Backend tests are defined under `api/tests/`. They are designed around dependency overrides so they can run without PostgreSQL in CI once FastAPI/pytest dependencies are installed.

## Phase boundary

Phase 1 intentionally stops before parsing/indexing files. Uploaded documents create a pending ingestion job and remain ready for the Phase 2 worker pipeline.
