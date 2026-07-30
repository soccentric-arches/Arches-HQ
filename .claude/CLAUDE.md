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

<!-- END loop-engine -->
