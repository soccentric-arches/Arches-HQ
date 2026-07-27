# Arches-HQ — Implementation Plan

Status: planning artifact, no code yet. Expands `PLAN.md` (phasing) and
`ARCHITECTURE.md` (system design) into concrete, sequenced engineering work:
module breakdown, schemas, API surface, milestones, and acceptance criteria
per phase. Read `CLAUDE.md`, `PLAN.md`, `ARCHITECTURE.md` first — this doc
does not repeat their rationale, only their conclusions, and goes one layer
deeper into "what gets built, in what order, and how we'll know it's done."

Open decisions this plan still depends on (tracked in `PLAN.md` §3): cloud
provider, single-deployment vs. per-customer, and human-auth IdP choice.
Where a decision is pending, this plan states the default it assumes and
what changes if the answer differs.

---

## 0. Repo & environment setup

Blocked on `PLAN.md` §0 (repo creation, needs your `gh` access). Once the
remote exists:

- `develop` branch per fleet convention; protected, PR-only merges to it once
  more than one person is committing.
- Directory skeleton (no code yet, just structure to agree on before Phase 1
  starts writing into it):
  - `api/` — FastAPI service (routers, models, db, auth, workers)
  - `agent-gateway/` — gRPC bidi service for device connections (separate
    deployable from `api/` per ARCHITECTURE.md §2, so it can scale/restart
    independently of the human-facing REST API)
  - `web/` — Vue 3 + Vite frontend
  - `proto/` — `archeshq.agent` proto definitions (own package, not shared
    with `Arches-HAL`/`Arches-Client`)
  - `migrations/` — Alembic (Postgres) migration scripts
  - `infra/` — Dockerfiles, docker-compose for local dev, deployment manifests
  - `docs/` — this plan, architecture doc, ADRs as decisions get made
- Local dev: `docker-compose.yml` bringing up Postgres, MinIO (S3-compatible,
  works for local dev regardless of eventual cloud choice), Redis (for
  Celery/arq), api, agent-gateway, web — so Phase 1 work is runnable before
  any cloud target is chosen.
- CI: lint + typecheck + unit tests on PR, from the first commit that has
  code (don't wait until Phase 2 to add CI).

**Acceptance:** `docker-compose up` brings up an empty-but-running stack;
CI passes on an empty scaffold PR.

---

## 1. Phase 1 — Backend skeleton + human auth + static device list

Goal: a deployable app with real auth and a real (if inert) device list.
No device ever connects yet.

### 1.1 Database schema (initial migration)

- `tenant(id, name, created_at)`
- `user(id, tenant_id, email, role[admin|operator|viewer], auth_subject_id, created_at)`
  — `auth_subject_id` is the IdP's subject claim if OIDC is chosen (see 1.2);
  nullable if built-in auth is chosen instead.
- `device(id, tenant_id, name, pairing_state[pending|authorized|disabled|revoked], created_at, last_seen_at nullable, online bool default false)`
  — telemetry/location/credential columns land in later phases; this phase
  only needs enough to render a list and a detail stub.
- `audit_log(id, tenant_id, actor_user_id, action, target_device_id nullable, payload jsonb, created_at)`
  — created now even though nothing writes to it yet except auth events
  (login) and device create, because retrofitting audit logging later is
  the kind of thing that gets skipped under deadline pressure.

All tenant-scoped tables carry `tenant_id` and every query path filters on
it — enforced at the ORM/query-builder layer (e.g. a base repository class
that requires a tenant context), not left to each handler to remember.

### 1.2 Auth

Default assumption per `ARCHITECTURE.md` §2: OIDC. Concretely for Phase 1:

- Stand up (or point at) an OIDC provider — if no IdP is chosen yet, use a
  self-hosted option (e.g. Keycloak) in the local/dev compose stack so
  Phase 1 isn't blocked on an external vendor decision. Swapping the IdP
  later only touches the OIDC client config, not the app's auth model,
  provided we don't hand-roll session logic that assumes a specific
  provider's claims shape.
- FastAPI dependency that validates the ID token / session, resolves
  `user.tenant_id`, and injects a `TenantContext` into every handler.
- Session: short-lived JWT issued by the API after OIDC login, stored in an
  httpOnly cookie for the Vue app (avoids localStorage token handling in
  the frontend).
- Roles enforced via a decorator/dependency (`admin` for device
  provisioning/disable/reset, `operator` for day-to-day ops, `viewer`
  read-only) — define the three roles' permission matrix explicitly as a
  table in this doc before writing the decorator, so it's one source of
  truth:

  | Action | viewer | operator | admin |
  |---|---|---|---|
  | View device list/detail | yes | yes | yes |
  | View telemetry/logs | yes | yes | yes |
  | Provision new device | no | yes | yes |
  | Trigger backup | no | yes | yes |
  | Trigger restore | no | no | yes |
  | Disable device | no | no | yes |
  | Factory reset | no | no | yes |
  | Rotate/revoke credential | no | no | yes |
  | Manage users/roles | no | no | yes |

### 1.3 API surface (Phase 1 subset)

- `POST /auth/callback` (OIDC redirect handler), `POST /auth/logout`
- `GET /devices` — paginated, tenant-scoped, sortable by `online` then
  `last_seen_at`/`name` (matches `ARCHITECTURE.md` §5 requirement)
- `GET /devices/{id}` — detail stub (no live telemetry yet)
- `POST /devices` — creates a `pending` device record with a placeholder
  name (pairing token generation is Phase 2, but the record + UI list entry
  should exist now so Phase 2 only adds the token mechanics)
- `GET /users`, `POST /users/invite` (admin only)
- `GET /audit-log` (admin only, paginated)

### 1.4 Frontend (Vue)

**Design system:** UI is shadcn-inspired — clean, minimal, low-chrome
component style (subtle borders over heavy shadows, generous whitespace,
restrained color use, neutral-gray base palette with a single accent
color for primary actions/status). Concretely:

- shadcn's components are React/Tailwind-native; since this repo is Vue,
  use a shadcn-style Vue port (e.g. `shadcn-vue`) or hand-roll the small
  set of primitives (button, input, table, dialog, dropdown, badge, card,
  tabs) on top of Tailwind directly, matching shadcn's tokens (radius,
  spacing, border/shadow scale) rather than pulling in a heavier
  component library (Vuetify, Element Plus, etc.) that fights the
  aesthetic.
- Tailwind CSS as the styling layer (matches shadcn's approach and is a
  natural fit with Vite).
- **Light theme only.** No dark-mode toggle, no `prefers-color-scheme`
  branch, no dark CSS variables shipped at all — this is a deliberate
  scope cut, not a "dark mode later" placeholder. Don't build the
  theming abstraction (CSS variable swap, theme context/store) that
  dark-mode support would need; that's wasted work for a feature that
  isn't happening.
- Status colors (online/offline, alarm severity, pairing state) use a
  small, consistent palette against the light background — e.g. muted
  green/red/amber accents rather than saturated "alert box" colors, in
  keeping with shadcn's restrained visual language.
- This design-system baseline is set once in Phase 1 (login, device list,
  device detail shell) and every subsequent phase's screens (telemetry
  charts, fault/alarm feeds, log lists, ops dialogs) reuse the same
  primitives rather than introducing new visual patterns per phase.

- Login flow (redirect to IdP, land back authenticated)
- Device list page: table, online/offline badge (always offline in Phase 1
  since no agent exists yet — acceptable, flag it in the UI or a banner
  rather than faking data), search/filter by name
- Device detail page: stub fields only (name, pairing state, created date)
- Basic app shell/nav (devices, users, audit log) — no telemetry/logs/ops
  screens yet, those come in their respective phases

### 1.5 Cloud target

Stand up whatever the answer to `PLAN.md` §3 turns out to be: managed
Postgres, S3-compatible bucket, container hosting (ECS/Cloud Run/AKS/VM +
compose — pick based on team's existing ops familiarity, not novelty).
Containerize `api` and `web` (agent-gateway has no traffic yet, can wait
for Phase 2 to deploy).

**Acceptance (Phase 1 exit criteria):**
- An admin can log in, invite another user, create a device record, and see
  it in the list.
- Every table has `tenant_id`; a manual test with two tenants confirms zero
  cross-tenant leakage in list/detail endpoints.
- Audit log has entries for login and device creation.
- Deployed to the chosen cloud target, reachable over HTTPS.

---

## 2. Phase 2 — Device pairing + presence

Goal: a real device (or a scripted stand-in, if `Arches-Configuration`'s HQ
agent isn't ready yet) can pair and show up as online/offline live.

### 2.1 Proto & gateway service

- Define `archeshq.agent` proto: bidi stream `Connect(stream AgentFrame)
  returns (stream ServerFrame)`, plus frame types: `Heartbeat`,
  `TelemetrySample` (stub in Phase 2, filled out in Phase 3),
  `PairingHandshake`. Keep this proto in this repo, versioned
  independently — no shared package with `Arches-HAL`/`Arches-Client`
  (per `ARCHITECTURE.md` §7).
- `agent-gateway` service: accepts TLS connections, validates the device
  credential (or pairing token on first connect), maintains an in-memory
  (Redis-backed if gateway is horizontally scaled) map of `device_id →
  connection`, updates `device.online`/`last_seen_at` on heartbeat.
- Stale-connection sweep job (Celery/arq beat, every N seconds): any device
  marked online whose `last_seen_at` exceeds 2x heartbeat interval flips to
  offline. This is the backstop for hard power loss where no clean
  disconnect frame arrives (`ARCHITECTURE.md` §3 step 5).

### 2.2 Pairing token flow

- `device_credential(id, device_id, token_hash, kind[pairing|long_lived], expires_at nullable, revoked_at nullable, created_at)`
  — store hashes, never raw tokens, same discipline as password storage.
- `POST /devices` (extended from Phase 1) now generates a single-use
  pairing token (random 32+ bytes, short expiry e.g. 15 min), returns it
  once to the admin UI for manual entry into WebConfig.
- `agent-gateway` first-connect handshake: device presents pairing token →
  gateway validates (unexpired, unused, matches a `pending` device) →
  issues a long-lived device credential over the same stream → flips
  `device.pairing_state` to `authorized` → device stores the long-lived
  credential locally (WebConfig's responsibility) and uses it for all
  future connections.
- Credential rotation/revocation endpoints (admin only): `POST
  /devices/{id}/credential/rotate`, `POST /devices/{id}/credential/revoke`
  — revoke immediately tears down any live connection for that device
  (gateway checks credential validity on each frame or via a revocation
  pub/sub channel, not just at connect time).

### 2.3 Cross-repo coordination (Arches-Configuration)

Track as its own scoped piece of work in `Arches-Configuration`, not
silently assumed here:
- New WebConfig section: HQ address + pairing token entry field.
- New WebConfig backend component (alongside `UpdateBackend`,
  `SystemdClient`): the outbound HQ agent — dials `agent-gateway`, sends
  heartbeats, stores the long-lived credential (needs secure local storage
  on-device — confirm what WebConfig already has for this, e.g. wherever
  it keeps other secrets).
- This is a dependency, not a blocker for HQ-side work: Phase 2 on the HQ
  side can be built and tested against a scripted test client that speaks
  the `archeshq.agent` proto, decoupling the two repos' timelines.

### 2.4 UI

- Device list: real online/offline badges, live update via WebSocket
  (`GET /ws/devices` pushes state-change events so the list doesn't need
  polling).
- Device detail: connection state, last-seen timestamp, pairing state,
  credential rotate/revoke buttons (admin only).
- "Add device" flow: generate token, show it once with a copy button and a
  clear "this won't be shown again" warning.

**Acceptance (Phase 2 exit criteria):**
- A test client (or real device, if Configuration's side is ready) can
  pair using a token and show up as online within one heartbeat interval.
- Killing the connection uncleanly (no disconnect frame) flips the device
  to offline within 2x heartbeat interval via the sweep job.
- Revoking a credential disconnects the device within a few seconds.
- Two-tenant leakage test extended to device connections: gateway rejects
  a credential presented for a device outside its issuing tenant (shouldn't
  be reachable via normal flow, but test the rejection path explicitly).

---

## 3. Phase 3 — Telemetry, faults/alarms, logs

Goal: device detail page becomes actually useful for fleet monitoring.

### 3.1 Telemetry

- `telemetry_sample(id, device_id, recorded_at, metric, value, tags jsonb)`
  — start with a simple wide-ish table; if/when volume demands it,
  reconsider partitioning by time or moving to a dedicated TSDB
  (Timescale extension on the same Postgres is the lowest-friction next
  step if needed — don't reach for a separate TSDB until Postgres actually
  struggles).
- Agent frame extension: `TelemetrySample` frames batched from the device
  (don't send one frame per metric per second — batch on a sane interval,
  e.g. every 30-60s, configurable).
- `GET /devices/{id}/telemetry?metric=&from=&to=` for chart data.
- UI: charts (CPU/mem/disk/network at minimum; extend per what
  `Arches-Configuration`'s WebConfig already aggregates, since HQ is
  relaying what the device already knows about itself, not inventing new
  monitoring).

### 3.2 Faults

Faults are raw, device-reported conditions — HQ records what the device
says, verbatim, with no interpretation layer.

- `fault(id, device_id, code, severity[info|warn|critical], message, raised_at, cleared_at nullable)`
- Device agent pushes fault-raised/fault-cleared frames as they happen
  (event-driven, not polled) so the UI reflects them close to real-time.
- WebSocket push to any connected UI session viewing that device (or fleet
  view) on fault raise — this is the "near-real-time" requirement from
  `ARCHITECTURE.md` §5.
- UI: fault feed per device (raw, unfiltered — every fault the device
  reports, regardless of whether it's alarm-worthy).

### 3.3 Alarms

Alarms are a separate, HQ-side construct: operator-configured rules that
watch faults and/or telemetry and decide when something is worth surfacing
and notifying on. A fault existing does not automatically mean an alarm
fires — that mapping is explicit and operator-controlled, not implicit
severity-based promotion.

- `alarm_rule(id, tenant_id, name, condition jsonb, notify_channels jsonb, enabled bool, created_at)`
  — `condition` covers both trigger types: fault-code match (e.g. "any
  fault with severity=critical") and telemetry-threshold match (e.g. "cpu_temp
  > 85 for 5 minutes"). Two condition kinds, one rule table, so the alarm
  evaluation worker doesn't need two separate pipelines.
- `alarm(id, alarm_rule_id, device_id, state[active|acknowledged|resolved], triggered_at, acknowledged_at nullable, acknowledged_by nullable, resolved_at nullable, source_fault_id nullable)`
  — an alarm has its own lifecycle independent of the fault that (maybe)
  triggered it: a fault can clear on the device while the alarm stays
  `active` until an operator acknowledges/resolves it, since "the device
  says it's fine now" and "an operator has confirmed this incident is
  handled" are different facts.
- Evaluation: fault-triggered alarms fire synchronously off the
  fault-raised frame (checked against enabled `alarm_rule`s for that
  tenant/device); threshold-triggered alarms are evaluated by the
  background worker on each telemetry write (or on a short poll interval
  if evaluating per-write is too chatty at scale).
- Notification on alarm trigger (not on fault raise) — email at minimum
  for Phase 3; Slack/webhook can be a later add-on, not blocking.
- UI: alarm feed per device + fleet-wide alarm feed, with
  acknowledge/resolve actions (operator role and above); a distinct
  fault feed (3.2) for the raw, unfiltered device-reported stream that
  alarms are built on top of.

### 3.4 Logs

- Device batches recent logs into a bundle (WebConfig's existing log
  aggregation, per `ARCHITECTURE.md` §1, is the source — HQ doesn't
  reinvent log collection, just receives bundles) and uploads to object
  storage over a dedicated (non-streaming) endpoint — a signed upload URL
  pattern (device requests one via the agent stream, then does a plain
  HTTPS PUT) keeps large blobs off the gRPC stream.
- `log_bundle(id, device_id, storage_url, size_bytes, uploaded_at, time_range_start, time_range_end)`
- `GET /devices/{id}/logs` lists bundles; `GET
  /devices/{id}/logs/{id}/download` issues a short-lived signed download
  URL.
- Search: Phase 3 minimum is "list + download," full-text search across
  log contents is a nice-to-have, not a blocker — note it as a Phase 3.5
  stretch rather than scope-creeping the phase.

**Acceptance (Phase 3 exit criteria):**
- Telemetry charts render real data from a connected test device.
- A simulated fault appears in the fault feed within a few seconds via
  WebSocket, without a page refresh.
- An `alarm_rule` matching that fault's severity produces an `active`
  alarm and sends a notification; acknowledging it in the UI updates
  `alarm.state` without affecting the underlying fault's `cleared_at`.
- A log bundle uploaded by a test device is downloadable from the UI.

---

## 4. Phase 4 — Operations (the fleet-management verbs)

Goal: HQ can actually change device state remotely, not just observe it.

### 4.1 OTA artifact repo

- `update_artifact(id, version, target_board_rev, storage_url, checksum, created_at)`
- `update_rollout(id, artifact_id, target[all|device_group|specific_devices], status, started_at, completed_at nullable)`
  plus a per-device rollout status join table (`update_rollout_device(rollout_id, device_id, status, applied_at nullable, error nullable)`)
  so partial-fleet rollout progress is trackable, not just fleet-wide
  pass/fail.
- Upload flow (admin): push a new artifact + metadata, target a rollout.
- Device side: `Arches-Configuration`'s `UpdateBackend`/RAUC flow needs to
  be pointed at HQ's artifact URLs (signed, time-limited per
  `ARCHITECTURE.md` §5) — this is a cross-repo change in Configuration,
  scope it there once HQ's artifact API is stable, not before.
- Rollout strategy for Phase 4: staged rollout (small % first, expand on
  success) is the safer default over "push to 100% at once" — worth
  building the targeting model to support staging from the start even if
  the first real rollout is manual/small.

### 4.2 Backup & restore

- Command pushed down agent stream (`TakeBackupNow`) → device uploads
  backup blob via the same signed-URL upload pattern as logs.
- `backup(id, device_id, storage_url, size_bytes, created_at, restored_at nullable)`
- Restore: admin selects a backup → command pushed with the backup's
  signed download URL → device (via WebConfig) applies it → HQ observes
  device reconnect/report as confirmation, not just "command sent."
- Every backup/restore action written to `audit_log` before the command is
  even sent (so there's a record even if the device never acknowledges,
  per `ARCHITECTURE.md` §6).

### 4.3 Provisioning, reset, disable

- Bulk pre-provisioning: allow creating N device records + pairing tokens
  before hardware ships (CSV import or simple bulk-create endpoint) —
  useful for fleets that provision in batches rather than one at a time.
- Factory reset: command over agent stream; device performs reset locally;
  HQ observes the device drop offline then re-pair (new pairing token
  required post-reset, since the reset presumably wipes the stored
  credential) — confirm this assumption against what Configuration's reset
  actually wipes before finalizing the flow.
- Disable: HQ-side enforcement only (`ARCHITECTURE.md` §5) —
  `agent-gateway` refuses/tears down the connection for any device whose
  `pairing_state = disabled`, checked on every connect and periodically
  for already-connected devices, regardless of credential validity. No
  device cooperation required, which is the point (a compromised or
  unresponsive device can still be cut off).

### 4.4 Location tracking

- Reported field in telemetry, not a separate subsystem: `location(lat,
  lon, accuracy_m, source[gnss|network], recorded_at)` alongside other
  telemetry.
- Explicitly hardware-dependent (per `ARCHITECTURE.md` §5 — `gnss` is a
  HAL module gated behind hardware availability). UI must handle "no
  location data" as a normal state, not an error, for devices without
  GNSS.

**Acceptance (Phase 4 exit criteria):**
- A rollout targeting a single test device completes and
  `update_rollout_device.status` reflects success.
- Backup → restore round-trip works against a test device and both steps
  are in the audit log.
- Disabling a device disconnects it even with a still-valid credential.
- Bulk-provisioning 10 device records via one action produces 10 usable
  pairing tokens.

---

## 5. Phase 5 — Hardening

Goal: ready for real fleets, not just demo-scale.

- **Credential lifecycle:** scheduled rotation reminders (not forced —
  flag devices with credentials older than N days in the UI), full
  revocation audit trail.
- **Audit log UI:** filter by actor/action/device/date range; this becomes
  much more load-bearing once Phase 4's destructive ops are live.
- **Rate limiting:** on `agent-gateway` (per-device connection attempt
  limits, to blunt a compromised device hammering reconnects) and on the
  REST API (per-tenant, to blunt abusive UI/API usage).
- **Load testing:** simulate fleet-scale concurrent device connections
  against `agent-gateway` — this is the component most likely to have a
  scaling cliff (in-memory connection map, heartbeat processing rate).
  Establish a concrete target (e.g. "N concurrent devices, heartbeat every
  30s, gateway CPU/mem stays within X") before calling this done, not just
  "it didn't fall over in a quick test."
- **Tenant isolation audit:** a dedicated pass (ideally by someone other
  than who wrote the original queries) re-checking every tenant-scoped
  table/endpoint against the Phase 1 leakage test, now that Phases 2-4
  have added many more endpoints.
- **Backup/DR for HQ itself:** Postgres backups, object storage
  replication/versioning — HQ holding fleet backups is only useful if HQ's
  own data survives an incident too.

**Acceptance (Phase 5 exit criteria):** load test target met and
documented; tenant isolation audit complete with sign-off; rate limits
verified to actually trigger under simulated abuse; HQ's own DR plan
documented and at least once tested (restore from a backup, not just
"backups exist").

---

## 6. Cross-cutting concerns (apply across all phases, not a separate phase)

- **Audit logging:** every state-changing admin action, from Phase 1
  onward — don't defer this to Phase 5, retrofitting is worse than doing
  it as each feature lands.
- **Tenant scoping:** every new table and endpoint added in any phase goes
  through the same "carries `tenant_id`, filtered at the query layer"
  discipline from Phase 1 — this is the single most important invariant
  in the whole system and the easiest one to accidentally violate under
  time pressure.
- **Cross-repo tracking:** Configuration-side work (HQ pairing section,
  outbound agent, UpdateBackend pointer) is tracked here as dependencies
  but scoped and executed in `Arches-Configuration`'s own planning docs —
  don't let HQ's plan silently assume Configuration work is done.
- **No dependency on Arches-HAL/Client/Server protos** — reconfirm this
  stays true at the end of each phase; it's an easy invariant to
  accidentally break by "just reusing that one proto message" under
  deadline pressure.

---

## 7. Sequencing summary

```
Phase 0: repo + scaffold + local dev stack        [blocked on gh access]
Phase 1: auth + static device list + deploy       [no device dependency]
Phase 2: pairing + presence                       [needs Configuration coordination, but
                                                     can proceed against a test client first]
Phase 3: telemetry + faults/alarms + logs         [depends on Phase 2 connection]
Phase 4: OTA + backup/restore + provisioning/     [depends on Phase 3 infra for artifact/
         reset/disable + location                  log storage patterns]
Phase 5: hardening                                [depends on all features existing to
                                                     harden]
```

Phases 3 and 4 within-phase items (e.g. telemetry vs. faults vs. logs in
Phase 3) can be parallelized across engineers once Phase 2's connection
plumbing exists, since they're independent frame types on the same
established stream — sequencing above is dependency order between phases,
not a claim that everything within a phase is serial.
