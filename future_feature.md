# Future features — HQ console evolution

Tracks the full console specification (top bar, primary nav, sidebar rules)
against what is **shipped today** vs. **planned**. Nothing here breaks the
current layout: shipped items were added in place; deferred items land in
later phases.

Legend: ✅ shipped · 🔜 next phase · 🔮 future / needs backend or design work

---

## Top bar (persistent)

| Feature | Status | Notes |
|---|---|---|
| Logo | ✅ | Brand mark links to Devices. |
| Tenant switcher | 🔮 | Single-tenant deployment today (`Dev Tenant`). Needs tenant CRUD + membership model; switcher UI slots into the top bar next to the brand. |
| Global search (serial, tag, IP, deployment ID) | ✅ (partial) | `/` focuses the search; backend `GET /devices?q=` matches name, serial, IP, hostname. **Tags and deployment-ID search need a tagging model + deployment IDs — 🔮.** |
| Fleet scope selector (org → site → group) | 🔮 | No org/site/group hierarchy yet. Needs a scope model + filters threaded through every list endpoint. |
| Alert bell with unread count | ✅ (partial) | Bell shows the count of **active** device alarms (`GET /alarms/active`, 30 s poll) and links to each device's Alarms page. True *unread/acknowledged-by-me* state needs per-user notification tracking — 🔮. |
| Active deployments indicator (spinner + count) | ✅ | In-progress rollout count (`GET /update/rollouts`, 30 s poll); links to Deployments. |
| Help / docs | ✅ (partial) | Help menu shows keyboard shortcuts. A real docs site / help center — 🔮. |
| User menu: profile | 🔮 | Menu shows email + role; a profile page (display name, password change) needs `PATCH /users/me`. |
| User menu: API keys | 🔮 | Needs personal API-token model (`api_key` table, scoped permissions, rotation) + docs for programmatic access. |
| User menu: theme | 🔮 | Design tokens are light-only by deliberate scope cut (see `web/src/assets/main.css`). Dark theme needs a token pass. |
| Sign out | ✅ | |

## Left sidebar / primary nav

HQ's primary nav lives in the persistent top bar (10-item cap respected:
Overview, Devices, Deployments, Alerts, Users†, Audit Log† — †admin-only).
Device-scoped navigation remains in the device detail sidebar.

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Overview — fleet health, version spread, active alerts | ✅ | `/overview`: device counts + online/offline, software version spread, active alarms, in-progress rollouts. Fleet *dashboards with metrics charts* — 🔮 (needs a metrics aggregation endpoint). |
| 2 | Devices — list, detail, groups, enrollment queue | ✅ (partial) | List + rich detail exist. **Device groups**, **tags**, and an **enrollment queue** (bulk pre-provision + claim flow) are 🔮 — backend has bulk-provision scaffolding (`BulkProvisionCreate`). |
| 3 | Deployments — releases, artifacts, rollouts, history | ✅ (partial) | `/deployments`: artifacts table + rollout status with per-device badges. Creation stays on device OTA pages for now; fleet-wide "new rollout" wizard — 🔮. |
| 4 | Configuration — templates, desired state, secrets, feature flags | 🔮 | Desired state exists per device (`device_config` sections). Templates (apply a config to many devices), secrets management, feature flags — all future; needs template model + scoped secret storage. |
| 5 | Monitoring — dashboards, metrics, logs | 🔮 | Per-device monitoring/telemetry/logs are shipped (device sidebar). Fleet-level dashboards need cross-device aggregation endpoints. |
| 6 | Alerts — active, rules, history | ✅ (partial) | `/alarm-rules` manages rules; active alarms live in the bell + device pages + overview. A dedicated Alerts page (active + history tables) is 🔜. |
| 7 | Automation — jobs, schedules, webhooks | 🔮 | No scheduler/webhook model yet. Candidate: arq jobs (redis) or a cron-style `automation_job` table. |
| 8 | Validation — Polaris/Vela results tied to device+version | 🔮 | **Differentiator — top-level placement reserved.** Needs the validation stack (Arches-Server/Dashboard) to publish results into HQ: new `validation_run` model + ingest endpoint + result pages. |
| 9 | Reports — compliance exports, SLA, audit log | 🔮 | Audit log exists (`/audit-log`). Compliance/SLA report generation + CSV/PDF export — future. |
| 10 | Settings — org, users, roles, SSO, integrations, API | ✅ (partial) | Users + audit exist. **Org settings, SSO, integrations pages** — 🔮. Device settings live per-device. |

## Bottom of sidebar

| Feature | Status | Notes |
|---|---|---|
| Environment badge (prod / staging) | ✅ | DEV/PROD pill in the top bar (`import.meta.env.DEV`); a real staging env is an infra concern. |
| Connection status to backend | ✅ | Polls `/api/healthz` every 30 s; green/red dot + Connected/Offline. |
| Version + changelog link | 🔮 | Version comes from `web/package.json` (still `0.0.0`); wire a real version into the build and link a CHANGELOG. |

## Rules

- ✅ Max 10 top-level items — currently 6 (+2 admin).
- 🔮 Sidebar collapsible to icons — HQ's nav is a top bar; if a left rail is
  added later, ship it with icon-collapse.
- ✅ Breadcrumbs for depth — device pages (`Devices / <name>`); more depth as
  pages grow.
- ✅ Keyboard: `/` search · `g d` devices · `g p` deployments (cheat sheet in
  the Help menu). Add more chords as pages land (`g o` overview, `g a` alerts).

## Phase 1 scope (agreed cut)

Shipped: **Overview, Devices, Deployments, Alerts** + top-bar search, bell,
deployment indicator, help, status cluster, keyboard shortcuts.
Cut to later phases: **Configuration, Automation, Reports** (sections 4, 7, 9),
plus everything marked 🔮 above.

## Suggested ordering for next phases

1. 🔜 Dedicated Alerts page (active + history) — small, completes section 6.
2. 🔜 Device groups + tags — unlocks scope selector + filtered lists.
3. 🔮 Validation ingestion (Arches-Server → HQ) — the differentiator.
4. 🔮 Multi-tenant + org/site/group scoping — biggest model change; do after
   groups.
5. 🔮 API keys + dark theme + profile — polish tier.