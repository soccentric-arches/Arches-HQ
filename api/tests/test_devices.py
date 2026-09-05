from datetime import datetime, timedelta, UTC

from app.models.device import Device
from app.models.device_credential import DeviceCredential
from app.models.enums import CredentialKind, UserRole
from tests.factories import login_as, make_tenant, make_user


async def test_device_list_sorted_online_then_recent_then_name(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    now = datetime.now(UTC)

    day_ago = now - timedelta(days=1)
    minute_ago = now - timedelta(minutes=1)
    db_session.add_all(
        [
            Device(tenant_id=tenant.id, name="offline-old", online=False, last_seen_at=day_ago),
            Device(tenant_id=tenant.id, name="online-b", online=True, last_seen_at=minute_ago),
            Device(tenant_id=tenant.id, name="online-a", online=True, last_seen_at=now),
        ]
    )
    await db_session.commit()

    login_as(client, admin)
    resp = await client.get("/devices")
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()["items"]]
    assert names == ["online-a", "online-b", "offline-old"]


async def test_create_device_writes_audit_log(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    await db_session.commit()

    login_as(client, admin)
    resp = await client.post("/devices", json={"name": "unit-1"})
    assert resp.status_code == 201
    assert resp.json()["device"]["pairing_state"] == "pending"

    audit_resp = await client.get("/audit-log")
    actions = [row["action"] for row in audit_resp.json()["items"]]
    assert "device.create" in actions


async def test_device_name_search(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    db_session.add_all(
        [
            Device(tenant_id=tenant.id, name="jetson-lab-1"),
            Device(tenant_id=tenant.id, name="jetson-lab-2"),
            Device(tenant_id=tenant.id, name="other"),
        ]
    )
    await db_session.commit()

    login_as(client, admin)
    resp = await client.get("/devices", params={"q": "jetson"})
    names = {d["name"] for d in resp.json()["items"]}
    assert names == {"jetson-lab-1", "jetson-lab-2"}


async def test_rename_device(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="old-name")
    db_session.add(device)
    await db_session.commit()

    login_as(client, admin)
    resp = await client.patch(f"/devices/{device.id}", json={"name": "new-name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "new-name"

    audit_resp = await client.get("/audit-log")
    actions = [row["action"] for row in audit_resp.json()["items"]]
    assert "device.rename" in actions


async def test_rename_device_requires_operator(client, db_session):
    tenant = await make_tenant(db_session)
    viewer = await make_user(db_session, tenant, UserRole.viewer)
    device = Device(tenant_id=tenant.id, name="old-name")
    db_session.add(device)
    await db_session.commit()

    login_as(client, viewer)
    resp = await client.patch(f"/devices/{device.id}", json={"name": "new-name"})
    assert resp.status_code == 403


async def test_rename_device_rejects_empty_name(client, db_session):
    tenant = await make_tenant(db_session)
    operator = await make_user(db_session, tenant, UserRole.operator)
    device = Device(tenant_id=tenant.id, name="keep")
    db_session.add(device)
    await db_session.commit()

    login_as(client, operator)
    resp = await client.patch(f"/devices/{device.id}", json={"name": "   "})
    assert resp.status_code == 422


async def test_factory_reset_queues_pending_command(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="wipe-me")
    db_session.add(device)
    await db_session.commit()

    login_as(client, admin)
    resp = await client.post(f"/devices/{device.id}/factory-reset")
    assert resp.status_code == 202
    assert resp.json()["ok"] is True

    audit_resp = await client.get("/audit-log")
    actions = [row["action"] for row in audit_resp.json()["items"]]
    assert "device.factory_reset.request" in actions


async def test_disable_device_sets_state_and_revokes(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="off", online=True)
    db_session.add(device)
    await db_session.flush()
    db_session.add(
        DeviceCredential(
            device_id=device.id,
            kind=CredentialKind.long_lived,
            token_hash="h" * 64,
        )
    )
    await db_session.commit()

    login_as(client, admin)
    resp = await client.post(f"/devices/{device.id}/disable")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pairing_state"] == "disabled"
    assert body["online"] is False

    audit_resp = await client.get("/audit-log")
    actions = [row["action"] for row in audit_resp.json()["items"]]
    assert "device.disable" in actions


async def test_device_out_exposes_agent_reported_info(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(
        tenant_id=tenant.id,
        name="sensor-1",
        ip_address="10.0.0.42",
        hostname="sensor-1.local",
        os_version="arches-os 2.1",
        sw_version="agent 0.9.3",
    )
    db_session.add(device)
    await db_session.commit()

    login_as(client, admin)
    resp = await client.get(f"/devices/{device.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ip_address"] == "10.0.0.42"
    assert body["hostname"] == "sensor-1.local"
    assert body["os_version"] == "arches-os 2.1"
    assert body["sw_version"] == "agent 0.9.3"


async def test_reboot_and_shutdown_queue_commands(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="rebootable")
    db_session.add(device)
    await db_session.commit()

    login_as(client, admin)
    paths = [("reboot", "device.reboot.request"), ("shutdown", "device.shutdown.request")]
    for path, _action in paths:
        resp = await client.post(f"/devices/{device.id}/{path}")
        assert resp.status_code == 202, path
        assert resp.json()["ok"] is True

    audit_resp = await client.get("/audit-log")
    actions = [row["action"] for row in audit_resp.json()["items"]]
    assert "device.reboot.request" in actions
    assert "device.shutdown.request" in actions


async def test_device_out_includes_agent_version_and_reported(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    db_session.add(
        Device(
            tenant_id=tenant.id,
            name="reported",
            agent_version="agent 1.2.0",
            reported={
                "hardware": {"soc": "sm8650"},
                "services": [{"name": "nginx", "state": "running"}],
            },
        )
    )
    await db_session.commit()

    login_as(client, admin)
    resp = await client.get("/devices")
    item = resp.json()["items"][0]
    assert item["agent_version"] == "agent 1.2.0"
    assert item["reported"]["hardware"]["soc"] == "sm8650"


async def test_device_search_matches_serial_ip_hostname(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    db_session.add_all(
        [
            Device(
                tenant_id=tenant.id,
                name="unit-a",
                serial="SN-778899",
                ip_address="10.1.1.10",
                hostname="alpha.local",
            ),
            Device(
                tenant_id=tenant.id,
                name="unit-b",
                serial="SN-111222",
                ip_address="10.1.1.77",
                hostname="beta.local",
            ),
        ]
    )
    await db_session.commit()

    login_as(client, admin)
    for query, expected in [
        ("SN-778899", "unit-a"),      # by serial
        ("10.1.1.77", "unit-b"),      # by IP
        ("beta.local", "unit-b"),     # by hostname
        ("unit-a", "unit-a"),         # by name (unchanged behavior)
    ]:
        resp = await client.get("/devices", params={"q": query})
        assert resp.status_code == 200, query
        names = [d["name"] for d in resp.json()["items"]]
        assert names == [expected], query
