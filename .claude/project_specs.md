# Arches-HQ — specs

Remote: `git@github.com:SiliconCentric/Arches-HQ.git` (origin configured; confirm reachability with `git ls-remote` before scoping a loop — branch-push fails late otherwise)
Parent project: Arches (target hardware: NVIDIA Jetson, Tegra family, L4T/JetPack OS, with an STM32 real-time co-processor)
Leaf type: `<Project>-HQ`
Status: REAL — actively built out (corrected 2026-07-28, was mislabeled PLANNING)

## What this is

Arches-HQ is the cloud fleet-management app for Arches devices: a multi-tenant web service (API + database + browser UI) that lets an operator view every paired device's status remotely and run operations against it (provisioning, updates, backup/restore, disable, factory reset, location tracking).

It is not the same thing as Arches-Configuration's on-device WebConfig UI (local, single-device, no cloud) or Arches-Dashboard (the standalone browser dashboard). HQ is the first leaf that is fleet-wide and cloud-hosted rather than device-resident.

Design docs: `PLAN.md` (roadmap, phases, decisions), `ARCHITECTURE.md` (system design, data model, protocols, security).

## Relationship to the rest of the fleet

* Device side lives in Arches-Configuration. HQ does not talk to Arches-HAL/Arches-Client protos directly — it pairs with the on-device WebConfig daemon, which already aggregates system status, logs, and owns the RAUC/update path. Adding a device-side "HQ" section to WebConfig (address/pairing config, token storage, outbound agent) is in scope for Arches-Configuration, coordinated from here.
* Reuses the Client→Server connectivity pattern, not the protos. Client streaming results to Server over a device-initiated, persistent, token-free bidi gRPC connection is the closest existing precedent for "device behind NAT reaches out to a cloud/host peer and stays connected." HQ's device-agent link is modeled on that shape (device dials out, persistent connection, presence = connection liveness) but is its own protocol with its own auth (device pairing token, not shared with `arches.stream`).
* Does not link Arches-HAL as a build subproject. HQ is a web app, not a native C++ consumer of the HAL/gRPC contracts — no `add_subdirectory`, no proto reuse. Treat any apparent similarity to Client/Server's proto sharing as coincidental, not a dependency.
* OTA artifact storage is new infra HQ owns, referenced by Arches-Configuration's existing `UpdateBackend`/RAUC flow — Configuration will need to point at HQ's artifact repo URL rather than (or in addition to) wherever it currently gets update artifacts.

See `ARCHITECTURE.md` for the full design and `PLAN.md` for phasing.

Part of the Arches project in the project-managers fleet. See `docs/project-managers.md` for the full 9-project / 8-leaf hierarchy and shared conventions.
