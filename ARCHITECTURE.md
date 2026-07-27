# Arches-HQ — Architecture & Design

Status: design draft, no code yet. Companion to `PLAN.md` (phasing) and the
leaf-level `CLAUDE.md` (fleet context).

## 1. What this system is

Arches-HQ is a multi-tenant, cloud-hosted fleet management app for Arches
devices (Jetson + STM32 units running `Arches-Configuration`/WebConfig and the
rest of the on-device stack). One HQ instance can see and operate on many
devices. It is the only leaf in the fleet that is not device-resident.

Two user-facing surfaces:

- **API** — backend service, database, device-facing connection endpoint.
- **Web UI** — browser dashboard: device list (online/offline), per-device
  detail pages, fleet operations.

One device-facing surface:

- **Device agent link** — a persistent, outbound connection from each paired
  device to HQ, used both as the presence signal (connected = online) and as
  the transport for telemetry/logs/commands.

## 2. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12, FastAPI (async) | Matches the FastAPI pattern other projects in the fleet already use for their device-facing dashboard (`Arches-Configuration`'s CLAUDE.md notes sibling projects run "Python/FastAPI/Vue" instead of Rust/WebConfig) — reduces the number of stacks the org supports. Async fits well with holding many concurrent long-lived device connections. |
| Device-agent transport | gRPC bidi stream (own proto package, e.g. `archeshq.agent`) over TLS | Mirrors the Client→Server shape (device dials out, persistent stream, presence = liveness) that's already proven in this fleet, without reusing or depending on `Arches-HAL`'s protos — HQ's contract is independent. |
| Browser-facing API | REST/JSON (FastAPI routers) + WebSocket for live status pushes to the UI | Simple, cacheable, easy to authz per-tenant; WebSocket only for the "device came online/went offline" live updates on the list/detail pages. |
| Database | PostgreSQL | Cloud multi-tenant app with concurrent writes from many devices — the shape Postgres is built for. (Note: `Arches-Server` uses SQLite, but its own CLAUDE.md flags that as a deliberate deviation from the org's default Postgres reference — HQ should use the default, not copy Server's deviation.) |
| Object storage | S3-compatible (AWS S3 or self-hosted MinIO) | OTA update artifacts and device backups are blobs, not rows — keep them out of Postgres. |
| Frontend | Vue 3 + Vite | Same rationale as backend: aligns with the FastAPI/Vue pattern already established elsewhere in the fleet, one less stack to onboard people onto. |
| Auth (human users) | OAuth2/OIDC (e.g. via an identity provider) + session/JWT for the API | Standard multi-tenant SaaS pattern; avoids rolling bespoke user auth. |
| Auth (devices) | Opaque pairing token, minted by HQ, entered into `Arches-Configuration`'s new HQ section | Device never gets a user credential; token is scoped to exactly one device record and revocable independent of user auth. |
| Deployment | Containerized (Docker), one container per service (api, agent-gateway, web, worker) behind a reverse proxy/load balancer | Straightforward to run on any cloud VM or k8s later; matches "runs on cloud" requirement without overcommitting to a specific provider yet. |
| Background jobs | Celery or FastAPI + arq (Redis-backed) | Needed for: OTA rollout orchestration, backup jobs, stale-device sweep (mark offline on missed heartbeat), alarm evaluation. |

Open decision, not blocking: specific cloud provider (AWS/GCP/Azure/self-hosted). The design above only assumes "Postgres + S3-compatible storage + container runtime," all of which exist on any of them — provider choice can be deferred to Phase 1 deployment planning (see PLAN.md).

## 3. Device pairing & connectivity

1. Operator adds a device in the HQ web UI → HQ generates a **pairing token**
   (random, single-use, short expiry) and a device record in `pending` state.
2. Operator (or a provisioning flow) enters the token + HQ address into a new
   **HQ section** inside `Arches-Configuration`'s WebConfig UI.
3. WebConfig's new HQ client (a small Rust component alongside the existing
   `UpdateBackend`/`SystemdClient` backends) dials out to HQ over TLS using
   the token, HQ validates it, flips the device record to `authorized`, and
   the pairing token is exchanged for a long-lived **device credential**
   (rotatable, revocable from the HQ UI).
4. From then on, WebConfig's HQ agent holds a **persistent outbound
   connection** (gRPC bidi stream) to HQ, sending a heartbeat + telemetry
   frames and receiving commands (backup, restart, disable, etc.) pushed down
   the same stream.
5. **Presence = connection state.** Device is "online" exactly while its
   stream is live and heartbeats are current within a threshold (e.g. missed
   2 heartbeat intervals → mark offline); a background sweep job enforces
   this so a hard power-loss (no clean disconnect) still flips to offline.

This is a device-initiated connection deliberately, so devices behind NAT/no
inbound port forwarding still work — same reasoning as the existing
Client→Server design.

## 4. Data model (high level)

- `tenant` — top-level account/org boundary.
- `user` — human operator, belongs to a tenant, has a role (admin/operator/viewer).
- `device` — one row per physical unit: id, tenant_id, friendly name, pairing
  state (`pending`/`authorized`/`disabled`/`revoked`), last-seen timestamp,
  current online/offline flag, last known IP/location, hardware identity
  (serial, board rev if available from Configuration's board manifest).
- `device_credential` — device's long-lived auth material, rotatable, revocable.
- `telemetry_sample` — time-series (likely a separate time-series-friendly
  table/partitioning or an external TSDB later if volume demands it).
- `fault` / `alarm` — event records with severity, raised/cleared timestamps, device_id.
- `log_entry` or log blob pointer — high-volume logs likely go to object
  storage with an index row in Postgres, not raw text in Postgres.
- `update_artifact` — OTA image metadata (version, target board rev, storage
  URL, checksum) + `update_rollout` (which devices, target version, status).
- `backup` — backup metadata + storage URL, per device, with restore history.
- `audit_log` — every operator-triggered action (provision, disable, factory
  reset, restore) with actor, target device, timestamp — required for a
  fleet-ops tool doing destructive things remotely.

## 5. Feature-to-mechanism map

| Feature (from requirements) | Mechanism |
|---|---|
| Online/offline device list, sorted | `device.last_seen` + connection-state sweep job; UI queries sorted by state then name/last-seen. |
| Device detail page | REST endpoints scoped to `device_id`, tenant-authorized. |
| System status / IP / etc. | Reported in periodic telemetry frames from the device agent. |
| Telemetry | Streamed over the agent connection, written to `telemetry_sample`, exposed via API + charts in UI. |
| Faults / Alarms | Device agent pushes fault/alarm events over the stream (not polled) so they show up in near-real-time; also periodically reconciled. |
| Logs | Device agent uploads log bundles (batched, not per-line over the stream) to object storage; HQ indexes them for search/download. |
| Update / artifact repo | HQ **is** the artifact repo: S3-compatible storage + `update_artifact` table; Configuration's RAUC `UpdateBackend` is pointed at HQ's artifact URLs (signed, time-limited) instead of/in addition to its current source. |
| Backup and restore | Command pushed down the agent stream ("take backup now") → device uploads backup blob to HQ storage; restore is the same in reverse, "push this backup blob, apply it." |
| Device provisioning | Pairing flow (§3) plus optional bulk/pre-provisioning (pre-create device records + tokens before hardware ships). |
| Device reset / factory reset | Command over the agent stream; device (via WebConfig) performs the reset locally and HQ observes the reconnect/re-pair afterward. |
| Device disable | HQ-side flag: agent gateway refuses/tears down the stream for a `disabled` device regardless of credential validity — immediate, server-enforced, no device cooperation required. |
| Location tracking | Reported field in telemetry (GPS if hardware has it, else last-known network/IP-based location) — accuracy is device-capability-dependent, flag this as a hardware-dependent feature in PLAN.md rather than assuming GNSS is always present (note: `gnss` is one of the 35 HAL modules gated behind hardware availability per Arches-HAL's module list). |

## 6. Security notes

- Device credentials and pairing tokens are scoped per-device, never shared
  across the fleet — a compromised device can't be used to pivot to others.
- Every destructive operator action (disable, factory reset, restore) goes
  through `audit_log` before/regardless of success, so there's a record even
  if the device never acknowledges.
- Tenant isolation is enforced at the query layer (every table with device
  data carries `tenant_id`, every API handler filters by the authenticated
  user's tenant) — don't rely on the UI alone to scope access.
- Multi-tenancy: single deployment, isolated by row-level tenant_id, is the
  Phase 1 assumption; revisit if a customer requires physical isolation.

## 7. What HQ deliberately does not do

- Does not replace `Arches-Configuration`'s local WebConfig UI — that remains
  the on-device, no-cloud-required config surface.
- Does not link `Arches-HAL` as a build dependency or reuse its proto
  packages — no ODR/versioning coupling to the native gRPC contracts.
- Does not assume a specific cloud provider yet (see §2 open decision).
