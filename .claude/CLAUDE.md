# Arches-HQ

Cloud fleet-management app: API, database and browser UI. An operator sees every paired device's
status remotely and runs operations against it. The only cloud-hosted leaf.

## How you work here

* Commands: `.claude/commands/` — test, lint, validate.
* Write: this is a web app. It does not link Arches-HAL, does not reuse `hal_service.proto` or `client_service.proto`, and is not part of the on-device build.
* Test: three suites — `test-api`, `test-gateway`, `test-web`. All three must pass.
* Migrations: alembic, and the gate enforces a **single head**. Check before adding one.

## How you validate

* Gate: `./.claude/validate.sh quick` (seconds) or `full` (adds build + tests). Run it before you claim done.
* Exit codes: `0` pass, `1`-`76` fail, `77` a check never ran. **77 is not a pass.**
* The gate and everything under `.claude/lib`, `hooks`, `commands`, `settings.json` is human-owned. Run it, never edit it.

## Do

* Keep the architectural boundary the gate checks: no on-device protos, no HAL coupling.
* Model the device link on Client-to-Server's shape (device dials out, persistent connection, presence = liveness) but keep it a separate protocol with its own pairing-token auth.
* Put device-side work in Arches-Configuration, coordinated from here — the HQ pairing section, token storage and outbound agent belong in that repo.
* Read `ARCHITECTURE.md` for the design and `PLAN.md` for phasing before changing structure.

## Don't

* **Don't link Arches-HAL or reuse its protos.** Any resemblance to Client/Server's proto sharing is coincidental, not a dependency.
* **Don't add a second alembic head.** The gate fails on it and the fix is a merge migration.
* **Don't confuse this with the two other UIs.** Arches-Configuration's WebConfig is local and single-device; Arches-Dashboard is a standalone browser app. HQ is fleet-wide and cloud-hosted.
* **Don't scope a loop here without confirming the remote is reachable** (`git ls-remote`) — `branch-push` fails late otherwise.

<!-- BEGIN loop-engine -->
## Do's and Don'ts (maintained by the Loop Engine)

Appended by the Loop Engine on loop close; curated by a human when approving a loop out of in-review/. Nothing outside this fence is engine-writable.

- (2026-07-30, loop 20260730-app-telemetry-daemon) Telemetry sample ingest added: `POST /devices/{device_id}/telemetry` (operator) and `GET /devices/{device_id}/telemetry/{sample_id}` (viewer) on `api/app/routers/telemetry.py`, backed by the pre-existing `telemetry_sample` table (phase1 migration). DO NOT rename the table to a bare `telemetry` without a human blessing — the loop's stated constraint said "new table named telemetry" but the table pre-existed as `telemetry_sample` and renaming would break the GET series router and risk a second alembic head. The accepted name is `telemetry_sample` pending human confirmation (see the loop's Lessons Learned F1).
- (2026-07-30, loop 20260730-app-telemetry-daemon) `make lint` was RED at baseline due to 8 pre-existing unused-import (F401) errors in `api/app/routers/devices.py`; cleared by `ruff check --fix` in the same commit as the telemetry work. If you see F401s reappear there, they are new, not pre-existing.
<!-- END loop-engine -->
