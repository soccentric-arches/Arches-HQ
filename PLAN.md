# Arches-HQ — Plan

Companion to `ARCHITECTURE.md` (system design). This doc covers repo setup and phasing.

## 0. Repo creation (action needed from you)

I don't have GitHub access or network egress to `github.com` from this
sandbox, so I could not create the `SiliconCentric/Arches-HQ` repo or push
this scaffold myself. To create it:

```bash
gh repo create SiliconCentric/Arches-HQ --private --description "Cloud fleet-management app for Arches devices"
```

Then, from this workspace folder:

```bash
cd Arches-HQ
git init
git remote add origin git@github.com:SiliconCentric/Arches-HQ.git
git add .
git commit -m "Initial plan + architecture docs"
git branch -M develop   # fleet convention: Makefile/repo_setup.sh expect a develop branch
git push -u origin develop
```

I've already added `Arches-HQ` to the root `Makefile` and `repo_setup.sh` so
`make init`/`make pull`/etc. pick it up once the remote exists.

## 1. Phasing

**Phase 0 — this pass (done):** `CLAUDE.md`, `PLAN.md`, `ARCHITECTURE.md`,
root-level wiring (Makefile, repo_setup.sh, root CLAUDE.md). No code.

**Phase 1 — backend skeleton:**
- FastAPI app, Postgres schema/migrations for `tenant`/`user`/`device`/`device_credential`/`audit_log`.
- Human auth (login, tenant scoping) — no device connectivity yet.
- Device list UI (Vue) showing seeded/manually-inserted devices, no live data.
- Pick and stand up actual cloud target (provider + Postgres + object storage), containerize.

**Phase 2 — device pairing + presence:**
- Pairing token flow end-to-end (HQ side).
- Coordinate with `Arches-Configuration` to add the HQ section (address + token entry) and the outbound agent — this is a cross-repo change, needs its own scoping there.
- Agent gateway service (gRPC bidi), heartbeat, online/offline sweep job.
- Device detail page shows live connection state.

**Phase 3 — telemetry / faults / alarms / logs:**
- Telemetry ingestion + storage + charts.
- Fault/alarm event pipeline, near-real-time UI updates (WebSocket push).
- Log bundle upload to object storage + search/download in UI.

**Phase 4 — operations:**
- OTA artifact repo (upload, versioning, rollout targeting) + Configuration's `UpdateBackend`/RAUC pointed at it.
- Backup/restore command + blob storage flow.
- Factory reset / disable / provisioning bulk flows.
- Location tracking (GNSS where available, else best-effort network location) — confirm per-device capability before assuming this is universal.

**Phase 5 — hardening:**
- Credential rotation/revocation flows, audit log review UI, rate limiting on the agent gateway, load testing for fleet-scale concurrent connections.

## 2. Cross-repo dependencies to track

- `Arches-Configuration`: needs a new HQ pairing section + outbound agent + (later) artifact-repo pointer for updates. Track as a tagged cross-repo item, not silently assumed.
- Root `Arches` Makefile/repo_setup.sh/CLAUDE.md: updated in this pass to include `Arches-HQ` as a 9th leaf.
- No dependency on `Arches-HAL`, `Arches-Client`, or `Arches-Server` protos — confirmed in ARCHITECTURE.md §7.

## 3. Open questions (need your call before Phase 1 locks in)

- Cloud provider: AWS/GCP/Azure/self-hosted?
- Single shared HQ deployment for all customers, or per-customer deployment? (Affects whether tenant isolation needs to be row-level only or also physical.)
- Identity provider for human auth: roll a simple built-in login first, or integrate an IdP (Auth0/Okta/etc.) from day one?
