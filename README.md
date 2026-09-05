# Arches-HQ

## Project Summary

Arches-HQ is the fleet-management control plane for Arches devices.

The repository combines a Python API under `api/`, a Python gRPC agent gateway under `agent-gateway/`, a web frontend under `web/`, database migrations, and Docker infrastructure.

The API models tenants, users, devices, credentials, telemetry, alarms, faults, backups, updates, audit logs, and pending commands. Routers expose device, telemetry, alarm, fault, log, backup, audit, user, authentication, and WebSocket workflows. Authentication is email+password login with JWT session cookies, request IDs, and tenant-aware data access.

The agent gateway contains generated protobuf bindings plus connection management, pairing, authentication, frame handling, stale-connection sweeping, and a gRPC server/servicer.

The API and gateway each have their own `pyproject.toml` and test suite. The web application is a Vite/TypeScript client with its own lint, build, and Vitest configuration. Alembic configuration and migration scripts establish the persistence boundary; Docker Compose provides local infrastructure.

Automated evidence is substantial but split across services.

Gateway tests cover frames, pairing, and stale sweeps. API tests cover alarms, devices, password authentication, pairing tokens, phase-three behavior, RBAC, telemetry, and tenant isolation.

The repository Makefile exposes install, run, test, and lint commands. The feature table reports implementation based on source and configuration and marks cross-service, deployment, and browser behavior as partial where repository tests do not prove it.

The control plane depends on database availability, migration order, credentials, broker or gateway connectivity, and browser deployment configuration.

Review tenant boundaries, reconnect behavior, credential rotation, WebSocket delivery, and the Compose environment before release.

No manual verification is implied by service tests.

## Features

| # | Name / Description | Implemented? | Test Coverage? | Manual Test |
|---:|---|---|---|---|
| 1 | Python API application and routing | Implemented | API pytest suite | [ ] Manual verification required |
| 2 | Tenant and user isolation | Implemented | `test_tenant_isolation.py`, `test_rbac.py` | [ ] Manual verification required |
| 3 | Email+password authentication with session cookies | Implemented | `test_auth.py` | [ ] Manual verification required |
| 4 | Device, telemetry, alarms, and faults | Implemented | Router tests | [ ] Manual verification required |
| 5 | Backups, updates, logs, and audit models | Implemented | Partial | [ ] Manual verification required |
| 6 | Agent gRPC gateway and pairing | Implemented | `test_frames.py`, `test_pairing.py` | [ ] Manual verification required |
| 7 | Stale connection sweeping | Implemented | `test_stale_sweep.py` | [ ] Manual verification required |
| 8 | Web frontend | Implemented | Partial: web test command configured | [ ] Manual verification required |
| 9 | Alembic migrations and Compose infrastructure | Implemented | Partial | [ ] Manual verification required |
| 10 | End-to-end deployed fleet workflow | Partial | No complete end-to-end claim | [ ] Manual verification required |

## Validation Commands

`make test`; `make lint`; `make run`. Service-specific commands are defined in the root Makefile and each package manifest.

## Existing Documentation

Cloud fleet-management app for Arches devices — view devices remotely, manage
pairing/authorization, and run fleet operations (telemetry, faults/alarms,
logs, OTA updates, backup/restore, provisioning, factory reset, disable,
location).

Status: **planning**. See [PLAN.md](PLAN.md) and [ARCHITECTURE.md](ARCHITECTURE.md).
