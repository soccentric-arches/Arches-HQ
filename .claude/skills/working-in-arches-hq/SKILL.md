---
name: working-in-arches-hq
description: How to build, run, test, and navigate the Arches-HQ repo (cloud fleet-management app for Arches devices). Use this whenever making code changes here — setting up the dev environment, running services, running tests/lint, adding migrations, or understanding how the pieces (api, agent-gateway, web) fit together and where the architectural boundaries are.
---

# Working in Arches-HQ

Arches-HQ is a multi-tenant cloud fleet-management app for Arches devices:
API + Postgres + browser UI, plus a gRPC gateway that devices dial into. It is
not the on-device WebConfig UI (that's Arches-Configuration) and it does
not link Arches-HAL or reuse its protos — see "Architectural boundaries"
below before reusing anything that looks like it belongs to the device side.

## Repo layout

- api/ — FastAPI REST/WebSocket service (app/): auth (email + password login),
  routers, SQLAlchemy models, Pydantic schemas, services. Tests in api/tests/.
- agent-gateway/ — gRPC server devices connect to (persistent, device-initiated,
  token-based pairing — see proto/archeshq/agent.proto). Tests in
  agent-gateway/tests/.
- web/ — Vue 3 + TypeScript frontend (Vite, vitest, eslint).
- migrations/ — Alembic migrations (single history, no branches — see below).
- infra/docker-compose.yml — Postgres, MinIO (S3), Redis for local dev.
- proto/archeshq/ — HQ's own device-agent protocol (distinct from any
  Arches-HAL/Arches-Client proto).

## Setup and running

```
make doctor    # check docker/python3/node are present
make install   # venv + api/agent-gateway deps (pip -e ...[dev]) + web npm install
make db-up     # start postgres/minio/redis, create archeshq_test db
make migrate   # alembic upgrade head
make seed EMAIL=you@example.com PASSWORD=changeme123   # dev tenant + admin login
make run       # start api (:8000) + agent-gateway (:50051) + web (:5173) in background
make logs      # tail background service logs
make stop      # stop what `make run` started (db keeps running)
make db-down   # stop db/minio/redis
```

Sign in at the printed LAN URL with the seeded email + password.

## Tests and lint

```
make test          # test-api + test-gateway + test-web
make test-api       # cd api && pytest (needs ARCHESHQ_TEST_DATABASE_URL / S3 env, see Makefile)
make test-gateway   # cd agent-gateway && pytest
make test-web       # cd web && vitest run
make lint           # ruff (api, agent-gateway) + eslint/vue-tsc (web)
```

Python: 3.12+, ruff for linting (line-length 100). api/pyproject.toml and
agent-gateway/pyproject.toml each declare their own deps/dev extras —
install with -e ./api[dev] -e ./agent-gateway[dev] (already done by make install).

## Validation gate (run before considering work done)

```
.claude/validate.sh quick   # architectural-boundary checks, single alembic head, linters
.claude/validate.sh full    # + make test-api / test-gateway / test-web
```

Exit codes: 0 pass, 1-76 fail (a check ran and failed — fix it), 77
means a check never ran (missing toolchain) — treat as blocked, not a pass.
validate.sh is human-owned; don't edit it — fix the underlying issue or note
it in the loop's Lessons Learned instead.

## Architectural boundaries (do not cross)

- No on-device proto reuse: never import/reference hal_service.proto,
  client_service.proto, or arches.stream from api/, agent-gateway/, or
  proto/. HQ's device-agent protocol (proto/archeshq/agent.proto) is
  modeled on the same "device dials out, persistent connection, presence =
  liveness" shape as Client→Server, but is its own protocol with its own auth
  (pairing token) — not a shared contract.
- No Arches-HAL build coupling: no add_subdirectory, no linking against
  Arches-HAL from any CMake/build file. HQ is a web app, not a native
  consumer of the HAL/gRPC contracts.
- Device-side changes (e.g. WebConfig pairing/agent config) belong in
  Arches-Configuration, coordinated from here — don't implement them in this repo.

## Migrations

Alembic history must stay a single linear chain (migrations/versions/).
validate.sh checks there is exactly one head (no unmerged branches); if you
add a migration, make sure down_revision chains from the current head.

## Adding a /claude command

See .claude/commands/validate.md for the pattern: YAML frontmatter
(description, argument-hint, allowed-tools), then instructions using
!command to execute and guidance on interpreting output/exit codes.
