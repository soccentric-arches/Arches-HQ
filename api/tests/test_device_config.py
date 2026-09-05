from app.models.device import Device
from app.models.enums import UserRole
from tests.factories import login_as, make_tenant, make_user


async def _setup(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="cfg")
    db_session.add(device)
    await db_session.commit()
    login_as(client, admin)
    return device


async def test_config_roundtrip_and_apply_command(client, db_session):
    device = await _setup(client, db_session)

    resp = await client.put(
        f"/devices/{device.id}/config/time",
        json={
            "config": {"mode": "ntp", "ntp_servers": ["pool.ntp.org"], "gnss": ["gps", "glonass"]}
        },
    )
    assert resp.status_code == 200
    assert resp.json()["config"]["mode"] == "ntp"

    # Unset section reads as empty, not 404.
    resp = await client.get(f"/devices/{device.id}/config/network")
    assert resp.status_code == 200
    assert resp.json()["config"] == {}

    # Saved section reads back.
    resp = await client.get(f"/devices/{device.id}/config/time")
    assert resp.status_code == 200
    assert resp.json()["config"]["ntp_servers"] == ["pool.ntp.org"]

    # Audit trail written.
    audit_resp = await client.get("/audit-log")
    actions = [row["action"] for row in audit_resp.json()["items"]]
    assert "device.config.update" in actions


async def test_config_put_requires_operator(client, db_session):
    tenant = await make_tenant(db_session)
    viewer = await make_user(db_session, tenant, UserRole.viewer)
    device = Device(tenant_id=tenant.id, name="v")
    db_session.add(device)
    await db_session.commit()

    login_as(client, viewer)
    resp = await client.put(
        f"/devices/{device.id}/config/security", json={"config": {"ssh_enabled": True}}
    )
    assert resp.status_code == 403


async def test_config_unknown_section_404(client, db_session):
    device = await _setup(client, db_session)
    resp = await client.get(f"/devices/{device.id}/config/bogus")
    assert resp.status_code == 404