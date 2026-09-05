# storage/ — all persistent HQ data lives here

Everything the HQ deployment persists on disk is rooted in this folder
(configurable via `ARCHESHQ_STORAGE_DIR`; Docker bind-mounts it from here).
The HQ database and the per-device SQLite files are managed by the API /
alembic; the MinIO data dir is owned by its container.

    storage/
    ├── hq.sqlite            # the HQ database (SQLite, alembic-managed)
    ├── minio/               # MinIO object-store root (docker bind mount);
    │                        #   blob keys are per-device:
    │                        #   <bucket>/devices/<device-id>/log_bundle|backup/<oid>
    ├── ota/                 # OTA artifact staging (fleet-level images)
    ├── app/                 # API/gateway file storage (ARCHESHQ_STORAGE_DIR in docker)
    │   └── devices/<uuid>/
    │       └── device.sqlite
    └── devices/<uuid>/      # (host-run API writes here directly)
        └── device.sqlite    # portable SQLite mirror of the device's data

## Per-device SQLite

`POST /api/devices/<id>/export` mirrors the device's rows (identity,
telemetry, alarms, faults, log bundles, backups, config) into
`device.sqlite` — idempotent, safe to re-run. The file is the backup/import
unit: copy it off the server, or restore missing rows into the HQ database
with `POST /api/devices/<id>/import`. Download via
`GET /api/devices/<id>/export/download`.

In git? No — this folder is gitignored; back it up like any datastore.