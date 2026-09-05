"""Per-device SQLite export/import (storage/devices/<id>/device.sqlite)."""

import sqlite3

from datetime import datetime, UTC

from app.models.device import Device
from app.models.enums import UserRole
from app.models.telemetry import TelemetrySample
from tests.factories import login_as, make_tenant, make_user


def _sample(device_id, metric, value):
    return TelemetrySample(
        device_id=device_id, metric=metric, value=value, recorded_at=datetime.now(UTC)
    )

# The settings object is a pydantic BaseSettings instance cached by
# get_settings(); tests repoint storage_dir at a tmp dir through this
# fixture-style helper.
def _set_storage_dir(monkeypatch, tmp_path) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path / "storage"))


async def test_export_writes_per_device_sqlite(client, db_session, monkeypatch, tmp_path):
    from app.config import get_settings

    _set_storage_dir(monkeypatch, tmp_path)
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="export-me")
    db_session.add(device)
    await db_session.flush()
    db_session.add(_sample(device.id, "cpu_pct", 42.5))
    await db_session.commit()

    login_as(client, admin)
    resp = await client.post(f"/devices/{device.id}/export")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["size_bytes"] > 0

    db_path = get_settings().storage_dir + f"/devices/{device.id}/device.sqlite"
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT metric, value FROM telemetry").fetchall()
    meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    conn.close()
    assert rows == [("cpu_pct", 42.5)]
    assert meta["schema_version"] == "1"


async def test_import_restores_missing_rows(client, db_session, monkeypatch, tmp_path):
    from sqlalchemy import select

    _set_storage_dir(monkeypatch, tmp_path)
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="restore-me")
    db_session.add(device)
    await db_session.flush()
    db_session.add(_sample(device.id, "mem_pct", 60.0))
    await db_session.commit()

    login_as(client, admin)
    assert (await client.post(f"/devices/{device.id}/export")).status_code == 200

    # Simulate data loss: wipe the device's telemetry from the HQ database.
    await db_session.execute(
        TelemetrySample.__table__.delete().where(TelemetrySample.device_id == device.id)
    )
    await db_session.commit()

    resp = await client.post(f"/devices/{device.id}/import")
    assert resp.status_code == 200
    assert resp.json()["imported"]["telemetry"] == 1

    rows = (
        (
            await db_session.execute(
                select(TelemetrySample).where(TelemetrySample.device_id == device.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].metric == "mem_pct"


async def test_import_without_export_404s(client, db_session, monkeypatch, tmp_path):
    _set_storage_dir(monkeypatch, tmp_path)
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="never-exported")
    db_session.add(device)
    await db_session.commit()

    login_as(client, admin)
    resp = await client.post(f"/devices/{device.id}/import")
    assert resp.status_code == 404


async def test_export_requires_operator(client, db_session, monkeypatch, tmp_path):
    _set_storage_dir(monkeypatch, tmp_path)
    tenant = await make_tenant(db_session)
    viewer = await make_user(db_session, tenant, UserRole.viewer)
    device = Device(tenant_id=tenant.id, name="v")
    db_session.add(device)
    await db_session.commit()

    login_as(client, viewer)
    resp = await client.post(f"/devices/{device.id}/export")
    assert resp.status_code == 403