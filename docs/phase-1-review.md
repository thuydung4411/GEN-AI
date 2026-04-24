# Phase 1 Review Notes

## Scope delivered

- Greenfield monorepo scaffold for `web`, `api`, `worker`, `infra`, and `docs`
- Supabase-based login shell in the web app
- FastAPI upload, list, and job status APIs
- PostgreSQL schema for workspaces, workspace members, documents, document versions, and ingestion jobs
- Storage abstraction with local disk default and optional Supabase storage upload
- Worker placeholder reserved for Phase 2

## Assumptions locked for Phase 1

- One personal workspace is auto-provisioned per authenticated user on first API call
- Shared multi-user team workspaces are deferred until a later phase
- Uploaded files are accepted and queued, but not parsed or indexed yet
- `STORAGE_BACKEND=local` is the default for local review unless Supabase storage credentials are configured

## Manual review checklist

1. Sign in from the web app using a valid Supabase user
2. Upload a supported file type and confirm an immediate `pending` job is created
3. Refresh the dashboard and confirm the document row persists
4. Open the API directly and confirm `GET /v1/documents` only returns data for the current user workspace
5. Call `GET /v1/jobs/{id}` for the returned job and confirm `status=pending`

## Rollback point

- Phase 1 only introduces foundational routes and schema
- If a change regresses upload flow, the safest rollback is to revert only the Phase 1 scaffold before moving into ingestion logic
