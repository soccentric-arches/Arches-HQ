"""Per-device persistent storage on the filesystem.

Layout under ``settings.storage_dir`` (Docker bind-mounts ./storage):

    storage/
    ├── postgres/         # Postgres data dir (docker bind mount)
    ├── minio/            # MinIO object store root (docker bind mount)
    ├── ota/              # OTA artifact staging area (fleet-level images)
    └── devices/<uuid>/   # one folder per device:
        └── device.sqlite #    portable SQLite mirror of the device's data

The SQLite file is the import/backup unit: export_device() upserts the
device's rows from Postgres (idempotent, INSERT OR REPLACE by row id), and
import_device() reads rows back into Postgres that are missing there. The
file can be copied off the server and later restored.
"""

import json
import sqlite3
import uuid
from datetime import datetime, UTC
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backup import Backup
from app.models.device import Device
from app.models.device_alarm import DeviceAlarm
from app.models.device_config import DeviceConfig
from app.models.fault import Fault
from app.models.log_bundle import LogBundle
from app.models.telemetry import TelemetrySample

SCHEMA_VERSION = "1"

_SQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS device (
    id TEXT PRIMARY KEY, name TEXT, pairing_state TEXT, online INTEGER,
    serial TEXT, board_rev TEXT, ip_address TEXT, hostname TEXT,
    os_version TEXT, sw_version TEXT, agent_version TEXT, reported TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS telemetry (
    id TEXT PRIMARY KEY, metric TEXT NOT NULL, value REAL NOT NULL,
    recorded_at TEXT NOT NULL, tags TEXT
);
CREATE TABLE IF NOT EXISTS alarms (
    id TEXT PRIMARY KEY, major_id INTEGER, sub_section INTEGER,
    fault_type INTEGER, severity INTEGER, alarm_code INTEGER,
    state TEXT, triggered_at TEXT, resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS faults (
    id TEXT PRIMARY KEY, code TEXT, severity TEXT, message TEXT,
    raised_at TEXT, cleared_at TEXT
);
CREATE TABLE IF NOT EXISTS log_bundles (
    id TEXT PRIMARY KEY, size_bytes INTEGER, uploaded_at TEXT,
    time_range_start TEXT, time_range_end TEXT
);
CREATE TABLE IF NOT EXISTS backups (
    id TEXT PRIMARY KEY, size_bytes INTEGER, created_at TEXT, restored_at TEXT
);
CREATE TABLE IF NOT EXISTS config (
    section TEXT PRIMARY KEY, config TEXT NOT NULL, updated_at TEXT NOT NULL
);
"""


def device_dir(storage_dir: str | Path, device_id) -> Path:
    return Path(storage_dir) / "devices" / str(device_id)


def device_db_path(storage_dir: str | Path, device_id) -> Path:
    return device_dir(storage_dir, device_id) / "device.sqlite"


def _iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None


def _upsert(conn: sqlite3.Connection, table: str, row: dict) -> None:
    cols = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})", tuple(row.values())
    )


async def export_device(session: AsyncSession, device: Device, storage_dir: str | Path) -> Path:
    """Mirror the device's Postgres rows into its SQLite file. Idempotent:
    repeated exports refresh the same file (INSERT OR REPLACE by id)."""
    db_path = device_db_path(storage_dir, device.id)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SQL_SCHEMA)

        _upsert(
            conn,
            "device",
            {
                "id": str(device.id),
                "name": device.name,
                "pairing_state": device.pairing_state.value,
                "online": int(device.online),
                "serial": device.serial,
                "board_rev": device.board_rev,
                "ip_address": device.ip_address,
                "hostname": device.hostname,
                "os_version": device.os_version,
                "sw_version": device.sw_version,
                "agent_version": device.agent_version,
                "reported": json.dumps(device.reported) if device.reported else None,
                "created_at": _iso(device.created_at),
            },
        )

        samples = (
            (
                await session.execute(
                    select(TelemetrySample).where(TelemetrySample.device_id == device.id)
                )
            )
            .scalars()
            .all()
        )
        for s in samples:
            _upsert(
                conn,
                "telemetry",
                {
                    "id": str(s.id),
                    "metric": s.metric,
                    "value": s.value,
                    "recorded_at": _iso(s.recorded_at),
                    "tags": json.dumps(s.tags) if s.tags else None,
                },
            )

        for a in (
            (await session.execute(select(DeviceAlarm).where(DeviceAlarm.device_id == device.id)))
            .scalars()
            .all()
        ):
            _upsert(
                conn,
                "alarms",
                {
                    "id": str(a.id),
                    "major_id": a.major_id,
                    "sub_section": a.sub_section,
                    "fault_type": a.fault_type,
                    "severity": a.severity,
                    "alarm_code": a.alarm_code,
                    "state": a.state.value,
                    "triggered_at": _iso(a.triggered_at),
                    "resolved_at": _iso(a.resolved_at),
                },
            )

        for f in (
            (await session.execute(select(Fault).where(Fault.device_id == device.id)))
            .scalars()
            .all()
        ):
            _upsert(
                conn,
                "faults",
                {
                    "id": str(f.id),
                    "code": f.code,
                    "severity": f.severity.value,
                    "message": f.message,
                    "raised_at": _iso(f.raised_at),
                    "cleared_at": _iso(f.cleared_at),
                },
            )

        for b in (
            (await session.execute(select(LogBundle).where(LogBundle.device_id == device.id)))
            .scalars()
            .all()
        ):
            _upsert(
                conn,
                "log_bundles",
                {
                    "id": str(b.id),
                    "size_bytes": b.size_bytes,
                    "uploaded_at": _iso(b.uploaded_at),
                    "time_range_start": _iso(b.time_range_start),
                    "time_range_end": _iso(b.time_range_end),
                },
            )

        for b in (
            (await session.execute(select(Backup).where(Backup.device_id == device.id)))
            .scalars()
            .all()
        ):
            _upsert(
                conn,
                "backups",
                {
                    "id": str(b.id),
                    "size_bytes": b.size_bytes,
                    "created_at": _iso(b.created_at),
                    "restored_at": _iso(b.restored_at),
                },
            )

        for c in (
            (await session.execute(select(DeviceConfig).where(DeviceConfig.device_id == device.id)))
            .scalars()
            .all()
        ):
            _upsert(
                conn,
                "config",
                {
                    "section": c.section,
                    "config": json.dumps(c.config),
                    "updated_at": _iso(c.updated_at),
                },
            )

        _upsert(conn, "meta", {"key": "exported_at", "value": datetime.now(UTC).isoformat()})
        _upsert(conn, "meta", {"key": "schema_version", "value": SCHEMA_VERSION})
        conn.commit()
    finally:
        conn.close()
    return db_path


async def import_device(session: AsyncSession, device: Device, storage_dir: str | Path) -> dict:
    """Restore rows from the device's SQLite file that are missing in
    Postgres (matched by primary key). Returns per-table insert counts.
    Only additive: nothing in Postgres is overwritten or deleted."""
    db_path = device_db_path(storage_dir, device.id)
    if not db_path.exists():
        raise FileNotFoundError(f"no export found at {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        counts: dict[str, int] = {}

        existing_telemetry = set(
            (
                await session.execute(
                    select(TelemetrySample.id).where(TelemetrySample.device_id == device.id)
                )
            ).scalars()
        )
        added = 0
        for r in conn.execute("SELECT * FROM telemetry").fetchall():
            if uuid.UUID(r["id"]) in existing_telemetry:
                continue
            session.add(
                TelemetrySample(
                    id=uuid.UUID(r["id"]),
                    device_id=device.id,
                    metric=r["metric"],
                    value=r["value"],
                    recorded_at=datetime.fromisoformat(r["recorded_at"]),
                    tags=json.loads(r["tags"]) if r["tags"] else None,
                )
            )
            added += 1
        counts["telemetry"] = added

        existing_faults = set(
            (
                await session.execute(
                    select(Fault.id).where(Fault.device_id == device.id)
                )
            ).scalars()
        )
        added = 0
        for r in conn.execute("SELECT * FROM faults").fetchall():
            if uuid.UUID(r["id"]) in existing_faults:
                continue
            session.add(
                Fault(
                    id=uuid.UUID(r["id"]),
                    device_id=device.id,
                    code=r["code"],
                    severity=r["severity"],
                    message=r["message"],
                    raised_at=datetime.fromisoformat(r["raised_at"]),
                    cleared_at=datetime.fromisoformat(r["cleared_at"]) if r["cleared_at"] else None,
                )
            )
            added += 1
        counts["faults"] = added

        existing_alarms = set(
            (
                await session.execute(
                    select(DeviceAlarm.id).where(DeviceAlarm.device_id == device.id)
                )
            ).scalars()
        )
        added = 0
        for r in conn.execute("SELECT * FROM alarms").fetchall():
            if uuid.UUID(r["id"]) in existing_alarms:
                continue
            session.add(
                DeviceAlarm(
                    id=uuid.UUID(r["id"]),
                    device_id=device.id,
                    major_id=r["major_id"],
                    sub_section=r["sub_section"],
                    fault_type=r["fault_type"],
                    severity=r["severity"],
                    alarm_code=r["alarm_code"],
                    state=r["state"],
                    triggered_at=datetime.fromisoformat(r["triggered_at"]),
                    resolved_at=(
                        datetime.fromisoformat(r["resolved_at"]) if r["resolved_at"] else None
                    ),
                )
            )
            added += 1
        counts["alarms"] = added
    finally:
        conn.close()
    return counts