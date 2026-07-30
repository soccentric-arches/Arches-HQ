# CLAUDE.md - Arches-HQ

See [project_specs.md](project_specs.md) for what this repo is and how it relates to the rest of the fleet.

## Commands

* API tests: `make test-api`
* Gateway tests: `make test-gateway`
* Web tests: `make test-web`

## Validation gate - .claude/validate.sh

```
./.claude/validate.sh quick   # seconds: architectural-boundary checks (no on-device protos, no HAL coupling), single alembic head, ruff + web linters
./.claude/validate.sh full    # + `make test-api`, `test-gateway`, `test-web`
```

Exit codes follow the fleet contract: 0 pass, 1-76 fail, 77 means a check never ran (missing toolchain) - which is not a pass. Runs automatically via the Stop hook in .claude/settings.json, on demand via /validate, and as part of any loop the engine executes here.

Human-owned: the Loop Engine runs this script and never edits it. If a check is wrong, fix it yourself or raise it in the loop's Lessons Learned.

<!-- BEGIN loop-engine -->
## Do's and Don'ts (maintained by the Loop Engine)

Appended by the Loop Engine on loop close; curated by a human when approving a loop out of in-review/. Nothing outside this fence is engine-writable.

- (2026-07-30, loop 20260730-app-telemetry-daemon) Telemetry sample ingest added: `POST /devices/{device_id}/telemetry` (operator) and `GET /devices/{device_id}/telemetry/{sample_id}` (viewer) on `api/app/routers/telemetry.py`, backed by the pre-existing `telemetry_sample` table (phase1 migration). DO NOT rename the table to a bare `telemetry` without a human blessing — the loop's stated constraint said "new table named telemetry" but the table pre-existed as `telemetry_sample` and renaming would break the GET series router and risk a second alembic head. The accepted name is `telemetry_sample` pending human confirmation (see the loop's Lessons Learned F1).
- (2026-07-30, loop 20260730-app-telemetry-daemon) `make lint` was RED at baseline due to 8 pre-existing unused-import (F401) errors in `api/app/routers/devices.py`; cleared by `ruff check --fix` in the same commit as the telemetry work. If you see F401s reappear there, they are new, not pre-existing.
<!-- END loop-engine -->
