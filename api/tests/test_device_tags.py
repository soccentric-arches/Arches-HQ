"""Freeform device tags."""

from app.models.device import Device
from app.models.enums import UserRole
from tests.factories import login_as, make_tenant, make_user


async def test_tags_roundtrip(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="tagged")
    db_session.add(device)
    await db_session.commit()

    login_as(client, admin)
    resp = await client.put(
        f"/devices/{device.id}/tags", json={"tags": ["pilot", "lab-3 ", "pilot"]}
    )
    assert resp.status_code == 200
    assert resp.json()["tags"] == ["lab-3", "pilot"]

    resp = await client.get(f"/devices/{device.id}/tags")
    assert resp.json()["tags"] == ["lab-3", "pilot"]

    # replace the set
    resp = await client.put(f"/devices/{device.id}/tags", json={"tags": ["production"]})
    assert resp.json()["tags"] == ["production"]

    # viewer cannot write
    viewer = await make_user(db_session, tenant, UserRole.viewer)
    await db_session.commit()
    login_as(client, viewer)
    resp = await client.put(f"/devices/{device.id}/tags", json={"tags": ["x"]})
    assert resp.status_code == 403
