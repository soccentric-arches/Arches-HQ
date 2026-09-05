# Future features — Fleet HQ full roadmap

The complete Fleet HQ feature list, mapped against what **ships today**.
Shipped items are live; everything else is phased below. Nothing here
requires breaking the current layout — new capabilities slot into existing
pages, the device sidebar, or new routes.

Legend: ✅ shipped · 🚧 partial (shipped, gaps listed) · 🔜 next phase · 🔮 future

---

## 1. Enrollment & Identity

| Feature | Status | Notes |
|---|---|---|
| Bulk pre-provisioning from CSV/API | 🚧 | `POST /devices/bulk` (one name per line, up to 100) + Devices → Bulk enroll dialog returns per-device pairing tokens. **CSV *file* upload parsing and the public REST API shape are 🔮.** |
| First-boot auto-enrollment with pre-shared token | 🚧 | Pairing-token flow exists (WebConfig dial-in). "First-boot unattended" variant needs the agent to auto-claim on zero-touch boot — 🔮 (Arches-Configuration). |
| Decommission (reject) | ✅ | `DELETE /devices/{id}` (admin) removes a pending/unwanted device + all data, audited. **Approve-without-token and an approval gate** — 🔮. |
| Auto-approve rules (cert CA, HW ID range, claim token) | 🔮 | Needs an auto-approve policy model evaluated by agent-gateway at pairing. |
| Device identity (UUID, serial, MAC, SoC ID, TPM handle) | 🚧 | UUID + serial live on the device row; MAC/SoC-ID/TPM handle need `reported` schema extension (AgentReport). |
| Certificate lifecycle (issue, renew, revoke, CRL/OCSP) | 🔮 | Today: opaque token credentials. Full PKI is a dedicated workstream. |
| Re-enrollment after board swap / RMA | 🔮 | Token rotate covers re-pairing; identity-preserving re-enrollment needs device-identity history. |
| Device cloning detection | 🔮 | Same credential, two concurrent connections → gateway can detect and flag; not implemented. |
| Decommission / quarantine / factory-reset-and-release | 🚧 | Disable + factory reset exist (device Power page). "Release" (delete + archive) — 🔮. |
| Ownership transfer between tenants | 🔮 | Needs cross-tenant admin tooling. |

## 2. Inventory & Metadata

| Feature | Status | Notes |
|---|---|---|
| Device list: search, sort, CSV export | 🚧 | Search across name/serial/IP/hostname (server-side), sortable columns + CSV export (client-side). Multi-column **filters, saved views** — 🔮. |
| Full attributes (HW rev, SoC, RAM/eMMC, bootloader/kernel/rootfs/app ver, geo, timezone, warranty…) | 🚧 | Serial, board rev, IP, hostname, OS/sw versions are live. The rest arrives via AgentReport schema extensions — 🔮. |
| Custom user-defined fields | 🔮 | Needs a per-tenant field schema + device `custom_fields` JSONB. |
| Tags (freeform) | ✅ | `GET/PUT /devices/{id}/tags` + chip editor on device Settings; key:value syntax + list filters — 🔮. |
| Static groups | ✅ | `POST/GET/DELETE /device-groups` + membership; UI on device Settings. Group targeting for rollouts shipped. |
| Dynamic groups (query-based) | 🔮 | Stored query + re-evaluation job. |
| Fleet hierarchy (org → site → line → device) | 🔮 | Largest model change; blocks the scope selector. |
| Bulk edit / bulk tag | 🔮 | Follows tags + groups. |
| Device notes / comments timeline | 🔮 | `device_note` table + timeline UI on the device page. |
| Attachments (photos, commissioning docs) | 🔮 | MinIO upload flow already exists — needs `device_attachment` records + UI. |
| Hardware change detection | 🔮 | Diff consecutive AgentReports; flag changes on the Hardware page. |

## 3. Connectivity & Health

| Feature | Status | Notes |
|---|---|---|
| Online / offline states | ✅ | Presence = open link; WS broadcast to the UI. |
| Degraded / never-seen states | 🚧 | `never-seen` is implicit (last_seen null); "degraded" needs a definition (missed heartbeats but connected) — 🔮. |
| Heartbeat + per-group timeout thresholds | 🚧 | Global threshold exists (`heartbeat_missed_threshold`); per-group — follows groups (🔮). |
| Last-seen timestamp | ✅ | Device pages + lists. |
| Connection duration, flap counter | 🔮 | Track session open/close events in the gateway. |
| Link type / signal / carrier / data usage | 🔮 | AgentReport `network` section (schema defined, agent-side work). |
| Latency / packet loss to HQ | 🔮 | Heartbeat round-trip measurement in gateway → telemetry metric. |
| Time sync status (NTP drift), clock skew warnings | 🔮 | Time & Sync config shipped; drift reporting needs agent metrics. |
| Watchdog reset counter, boot count, last boot reason | 🔮 | AgentReport `system` section. |

## 4. Software & Updates

| Feature | Status | Notes |
|---|---|---|
| Artifact repository (upload, versioning, checksum) | 🚧 | Artifacts CRUD + checksums + presigned download exist. Direct **file upload** to HQ (vs. URL registration) — 🔜. |
| Artifact types (rootfs, delta, container, FPGA, MCU, calibration) | 🔮 | Needs a `kind` field + per-type handling; apply_update payload is generic today. |
| Signing / signature verification / key rotation | 🔮 | Signature field + HQ-side verification service. |
| Compatibility matrix (artifact ↔ HW rev ↔ version) | 🚧 | `target_board_rev` is checked manually today; enforced matrix — 🔮. |
| Release channels (dev/beta/stable/LTS) | 🔮 | `channel` column + channel-aware targeting. |
| SBOM per release, CVE cross-reference, license report | 🔮 | SBOM upload + scanner integration. |
| Deployment targeting: single / group / fleet | ✅ (partial) | All / group / specific devices live. **Dynamic query targets** — 🔮. |
| Phased rollout (canary %, waves, soak) | 🔮 | Extend `UpdateRollout` with wave plan; gateway already handles per-device acks. |
| Auto-halt on failure-rate threshold | 🔮 | Rollout engine watches failure counts. |
| Abort mid-flight | ✅ | `POST /update/rollouts/{id}/abort` revokes undelivered commands, marks remaining devices failed. **Pause/resume** — 🔮. |
| Maintenance windows / blackouts | 🔮 | Per-device or per-group schedule honored by the rollout engine. |
| Per-device scheduling (deploy at 2am local) | 🔮 | Delayed PendingCommand delivery (scheduled_at column). |
| Deferred install (apply on next reboot) | 🔮 | Agent-side policy. |
| User-consent gate (on-device HMI) | 🔮 | Agent-side. |
| Delta updates, bandwidth cap, resume | 🔮 | Artifact diffing is a device-agent capability. |
| Pre/post-install health checks, auto-rollback | 🔮 | Agent executes checks; HQ already records per-device outcome. |
| Manual rollback to prior slot | 🔮 | Agent-side slot management. |
| Rollback-blocked flag (security fixes) | 🔮 | Rollout metadata. |
| Dependency ordering (bootloader → rootfs) | 🔮 | Artifact dependency graph. |
| Per-device deployment status (downloading %, installing, verifying…) | 🚧 | pending / applying / succeeded / failed exist; **fine-grained progress %** needs richer CommandAck payloads — 🔮. |
| Failure reason capture with logs attached | 🚧 | Error string is stored; **log attachment** — 🔮. |
| Retry (manual) | ✅ | `POST /update/rollouts/{id}/retry` re-queues failed devices. **Automatic retry/backoff** — 🔮. |
| Deployment history + release diff | 🚧 | History ✓ (rollouts list). **Diff between two releases** — 🔮. |
| Version distribution chart | ✅ | Overview → Software version spread. |
| Stragglers report (behind N versions) | 🚧 | Version-compliance card on Deployments (devices on latest artifact version); **straggler detail table** — 🔮. |

## 5. Configuration Management

| Feature | Status | Notes |
|---|---|---|
| Desired-state vs reported-state | 🚧 | Desired state ships (`device_config`); **reported-state per section** arrives via AgentReport diffs — 🔮. |
| Config push (KV / JSON / file drop) | 🚧 | JSON documents per section + ApplyConfig notify. |
| Per-device / group / fleet layering with precedence | 🔮 | Layered resolution engine. |
| Templates with variable substitution | 🔮 | Template table + render step on write. |
| Config versioning and rollback | 🔮 | Append-only config history. |
| Drift detection + auto-remediation | 🔮 | Diff desired vs AgentReport config sections. |
| Secrets injection (encrypted at rest) | 🔮 | Needs an encryption service + secret model — do not store secrets in `device_config` plaintext. |
| Feature flags per device / cohort | 🔮 | Section type + flag evaluation. |
| Calibration data store per unit | 🔮 | Critical for vision/medical — dedicated section + validation. |
| Certificate / CA bundle distribution | 🔮 | Config section + secure delivery. |

## 6. Telemetry & Monitoring

| Feature | Status | Notes |
|---|---|---|
| System metrics (CPU/RAM/disk/temp/network) | 🚧 | Ingest + per-device charts live; metric catalog is freeform — naming conventions for system metrics — 🔮. |
| App / domain metrics (fps, inference latency, CAN errors…) | ✅ (mechanism) | Arbitrary named metrics ingest + chart. |
| Sample rate + retention tiers | 🔮 | Retention policies on `telemetry_sample`. |
| Store-and-forward buffering offline | 🔮 | Device-agent capability (queue + replay). |
| Downsampling / rollups | 🔮 | Continuous rollup job. |
| Charts: time ranges, multi-device overlay, fleet percentiles | 🚧 | Time ranges + live polling shipped; **overlay + percentiles** — 🔮. |
| Fleet / per-device / custom dashboards | 🚧 | Per-device dashboards shipped; **fleet dashboards + custom (user-built) dashboards** — 🔮. |
| Anomaly detection / baselines | 🔮 | Statistical job over telemetry. |
| This device vs group median comparison | 🔮 | Follows groups. |

## 7. Alerting

| Feature | Status | Notes |
|---|---|---|
| Threshold rules (static) | ✅ | Alarm rules engine (fault-code rules today; metric thresholds — 🔮). |
| Dynamic thresholds, composite conditions, duration qualifiers | 🔮 | Rule DSL extension ("cpu > 90% for 10min"). |
| Severity levels | ✅ | info / warn / critical. |
| Routing by group / on-call schedule | 🔮 | Follows groups + escalation model. |
| Channels: email / SMS / Slack / PagerDuty / webhook | 🔮 | Needs notification-channel model + workers. |
| Dedup, grouping, flap suppression | 🔮 | Alarm engine extension. |
| Snooze / acknowledge / resolve | 🚧 | Device-alarm clear + rule-alarm **acknowledge/resolve shipped** (Alerts page); **assign/snooze** — 🔮. |
| Escalation policy | 🔮 | On-call rotation model. |
| Alert history + MTTR reporting | 🚧 | Rule-based alarm history fleet-wide shipped (`GET /alarms`); **MTTR reporting** — 🔮. |
| Maintenance-mode suppression during deployments | 🔮 | Links rollouts → alarm suppression. |

## 8. Logs & Diagnostics

| Feature | Status | Notes |
|---|---|---|
| Live log tail | 🚧 | UI + tabs shipped; **streaming** needs the agent protocol (Arches-Configuration). |
| Historical query + full-text search | 🚧 | Bundles (download) shipped; **queryable log store** — 🔮. |
| Remote log-level control | 🔮 | Config section (`system`). |
| On-demand log bundle pull | ✅ | Upload request → presigned URL → bundle row → download. |
| Crash dumps / coredumps + symbolication | 🔮 | Artifact type + symbol server. |
| Kernel panic capture from persistent store | 🔮 | Agent capability. |
| On-demand dmesg / unit status / process list | 🔮 | AgentReport on demand or command + result frame. |
| Trace / profile capture (perf, ftrace) | 🔮 | Agent capability. |
| Auto diagnostics on failure event | 🔮 | Rule: fault event → request log bundle. |
| Bandwidth-aware compressed upload | 🚧 | Compression via bundle upload exists; **bandwidth throttling** — 🔮. |

## 9. Remote Access

| Feature | Status | Notes |
|---|---|---|
| Browser terminal session | 🔮 | Big ticket: websocket relay through the gateway to the agent's shell. |
| File browser (up/down/delete) | 🔮 | Command + chunked transfer over the agent link. |
| Port forwarding / tunnel to on-device UI | 🔮 | Gateway relay service. |
| Remote reboot / shutdown | ✅ | Queued commands, delivered on heartbeat. |
| Service restart | 🔮 | Command kind + agent support. |
| Run arbitrary command with output capture | 🔮 | Command + result streaming (audit every invocation). |
| Session recording for audit | 🔮 | Follows terminal. |
| JIT access approval workflow | 🔮 | Approval model + gateway enforcement. |
| Session time limits / auto-disconnect | 🔮 | Relay policy. |
| Break-glass access with justification | 🔮 | Mandatory-audit workflow. |

## 10. Automation

| Feature | Status | Notes |
|---|---|---|
| Scheduled jobs (cron, fleet scope) | 🔮 | `automation_job` table + scheduler worker. |
| Event-driven rules (on-alert → action) | 🔮 | Rule engine hook into alarm creation. |
| Job templates with parameters | 🔮 | Follows job model. |
| Bulk execution + concurrency limits | 🔮 | PendingCommand fan-out already exists — needs orchestration. |
| Job status matrix + per-device results | 🔮 | Follows job model. |
| Webhooks in / out | 🔮 | Outbound webhook channel + inbound endpoint registry. |
| Public REST API (pagination, rate limits) | 🚧 | REST is session-cookie auth today; **API keys + rate limiting** — 🔮. |
| Streaming API / websocket for live events | 🚧 | Device-status WS exists; **general event stream** — 🔮. |
| CLI tool | 🔮 | Thin client over the public API once API keys land. |
| Terraform / IaC provider | 🔮 | After the public API stabilizes. |

## 11. Multi-Tenancy & Access Control

| Feature | Status | Notes |
|---|---|---|
| Organizations, projects, sub-fleets | 🔮 | Tenant model exists (single); hierarchy is the big one. |
| RBAC (owner/admin/operator/viewer/support) | 🚧 | 4 roles enforced on every route; **support role** — 🔮. |
| Custom roles with granular permissions | 🔮 | Permission-bit model. |
| Scoped access (this group only) | 🔮 | Follows groups. |
| SSO: SAML, OIDC | 🔮 | OIDC was replaced by password auth (deliberate); re-introduce as pluggable IdP. |
| SCIM provisioning | 🔮 | After SSO. |
| MFA enforcement | 🔮 | TOTP factor + policy. |
| Service accounts + API keys (scopes, expiry) | 🔮 | `api_key` table + auth dependency branch. |
| IP allowlisting | 🔮 | Tenant policy + middleware. |
| Session management / forced logout | 🔮 | Session store introspection. |
| Customer read-only portal | 🔮 | Scoped viewer tenant. |
| White-label branding per tenant | 🔮 | Theme tokens per tenant. |

## 12. Compliance & Audit

| Feature | Status | Notes |
|---|---|---|
| Append-only audit log (who, what, when) | 🚧 | Audit log shipped with actor/action/target/payload; **"from where" (IP) + before/after diffs** — 🔮. |
| Immutable deployment records | 🚧 | Audit entries on every rollout; **immutability enforcement (no UPDATE)** — 🔮. |
| Electronic signatures on critical actions (21 CFR Part 11) | 🔮 | Re-auth step + signature record on deploy/approve. |
| Two-person rule for prod deploys | 🔮 | Approval workflow on rollouts. |
| Evidence export packs for auditors | 🔮 | Bundle audit log + deployment records + SBOMs into one export. |
| Data residency controls | 🔮 | Per-tenant storage region. |
| Retention policies + legal hold | 🔮 | Retention job + hold flags. |
| SBOM archive per deployed release | 🔮 | Follows SBOM (section 4). |
| Traceability: serial → software bill → approval chain | 🔮 | Joins across existing records once SBOMs land. |
| UNECE R155/R156 artifacts | 🔮 | Automotive compliance pack. |
| IEC 62304 / ISO 14971 records | 🔮 | Medical compliance pack. |
| Incident report generation | 🔮 | Template over audit + alarms + deployments. |

## 13. Fleet Operations & Reporting

| Feature | Status | Notes |
|---|---|---|
| Fleet health score | ✅ | Overview: weighted online ratio, alarm pressure, rollout failures → 0–100. Formula tuning — ongoing. |
| Deployment success-rate trend | 🚧 | Success rate + per-device outcomes on the Deployments page; **trend over time** — 🔮. |
| Failure clustering (which HW rev fails) | 🔮 | Group rollout failures by board_rev. |
| Device lifecycle states | 🔮 | manufactured → shipped → commissioned → active → maintenance → retired. |
| RMA workflow + replacement linking | 🔮 | Lifecycle + identity re-enrollment. |
| Spare pool management | 🔮 | Follows lifecycle + groups. |
| Warranty / contract tracking | 🔮 | Device metadata (warranty expiry). |
| LTE data-usage reporting | 🔮 | AgentReport network counters. |
| Scheduled report email | 🔮 | Report model + mail worker. |
| Custom report builder | 🔮 | Last. |

## 14. Security

| Feature | Status | Notes |
|---|---|---|
| Secure boot / measured boot / dm-verity status | 🔮 | AgentReport `security` section (attestation values). |
| Firewall / open-port audit | 🚧 | Firewall config surface shipped (device Security page); **audit vs. reported state** — 🔮. |
| CVE scan against package manifest | 🔮 | SBOM + CVE feed (section 4). |
| Vulnerability dashboard per device | 🔮 | Follows CVE scan. |
| Emergency kill-switch / disable | ✅ | Disable endpoint (revokes credentials, cuts the link) + factory reset. |
| Anomalous behavior flags | 🔮 | Gateway-side connection analytics. |
| Debug interface state (JTAG/UART) warnings | 🔮 | AgentReport security section. |
| Key rotation orchestration | 🚧 | Credential rotation shipped; **cert/key infra rotation** — 🔮. |
| SIEM export / threat-detection hooks | 🔮 | Audit-log streaming export. |

## 15. Platform Non-Functionals

| Feature | Status | Notes |
|---|---|---|
| Scale to 100k+ devices | 🔮 | Postgres-grade store, partitioning, horizontal gateway. SQLite HQ is sized for dev/small fleets today; the per-device file layout keeps device data portable when that migration happens. |
| Offline-first device behavior, queueing | 🔮 | Agent capability (store-and-forward). |
| Graceful degradation when HQ unreachable | 🔮 | Agent capability. |
| HQ HA / disaster recovery | 🔮 | Storage/ is now the single backup unit — snapshot + replicate. |
| Rate limiting / backpressure on ingest | 🔮 | API middleware + gateway admission. |
| Thundering-herd protection (jittered backoff) | ✅ | HeartbeatAck interval is jittered ±30% per ack. |
| Bandwidth throttling per device / site | 🔮 | Gateway + agent. |
| Data export / no lock-in | ✅ (mechanism) | Per-device SQLite + CSV fleet export; full-fleet export — 🔮. |
| On-prem / air-gapped option | 🔮 | Compose stack is self-contained already; needs offline artifact delivery. |
| Localization / timezones | 🔮 | UI is English; timestamps are locale-formatted. |

---

## Phase plan

- **Phase 1 (shipped):** devices + rich detail (16 sections), telemetry + live monitoring,
  alarms + rules, OTA artifacts/rollouts with per-device delivery, backups, config sections,
  bulk enrollment, CSV export, fleet overview, RBAC, audit log, per-device SQLite,
  remote reboot/shutdown, fleet search, alert bell, keyboard shortcuts.
- **Phase 2 (next):** groups + tags, dedicated Alerts page, enrollment approval queue,
  deployment waves + pause/abort, config templates, artifact upload, log streaming.
- **Phase 3:** org/site hierarchy + scope selector, fleet dashboards, notification channels,
  security posture (AgentReport security section), SBOM/CVE.
- **Phase 4:** remote terminal + file access, automation engine, public API + CLI,
  SSO/MFA, compliance packs (12), white-label.
- **Your wedge:** traceability + compliance (section 12) alongside Polaris/Vela validation
  results on the same pane — generic vendors do 1–11 well and 12 poorly.