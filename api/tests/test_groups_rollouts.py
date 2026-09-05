"""Device groups, device decommission, rollout abort/retry."""

from app.models.device import Device
from app.models.enums import PairingState, UserRole
from app.models.update import UpdateArtifact
from tests.factories import login_as, make_tenant, make_user


async def _setup(client, db_session, authorized=True):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    d1 = Device(tenant_id=tenant.id, name="d1", pairing_state=PairingState.authorized)
    d2 = Device(tenant_id=tenant.id, name="d2", pairing_state=PairingState.authorized)
    db_session.add_all([d1, d2])
    await db_session.commit()
    login_as(client, admin)
    return tenant, admin, d1, d2


async def test_group_create_set_members_delete(client, db_session):
    _, _, d1, d2 = await _setup(client, db_session)

    resp = await client.post("/device-groups", json={"name": "line-1"})
    assert resp.status_code == 201
    group_id = resp.json()["id"]

    # duplicate name -> 409
    resp = await client.post("/device-groups", json={"name": "LINE-1"})
    assert resp.status_code == 409

    resp = await client.put(
        f"/device-groups/{group_id}/members", json={"device_ids": [str(d1.id), str(d2.id)]}
    )
    assert resp.status_code == 200
    assert len(resp.json()["device_ids"]) == 2

    resp = await client.get("/device-groups")
    groups = resp.json()["items"]
    assert len(groups) == 1 and len(groups[0]["device_ids"]) == 2

    resp = await client.delete(f"/device-groups/{group_id}")
    assert resp.status_code == 204
    resp = await client.get("/device-groups")
    assert resp.json()["items"] == []


async def test_group_membership_rejects_foreign_device(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    foreign = Device(tenant_id=tenant.id, name="other-tenant-device")
    # device of ANOTHER tenant
    other_tenant = await make_tenant(db_session)
    foreign.tenant_id = other_tenant.id
    db_session.add_all([foreign])
    await db_session.commit()

    login_as(client, admin)
    resp = await client.post("/device-groups", json={"name": "g"})
    group_id = resp.json()["id"]
    resp = await client.put(
        f"/device-groups/{group_id}/members", json={"device_ids": [str(foreign.id)]}
    )
    assert resp.status_code == 422


async def test_delete_device_decommissions(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="gone")
    db_session.add(device)
    await db_session.commit()

    login_as(client, admin)
    resp = await client.delete(f"/devices/{device.id}")
    assert resp.status_code == 204

    resp = await client.get(f"/devices/{device.id}")
    assert resp.status_code == 404

    audit_resp = await client.get("/audit-log")
    actions = [row["action"] for row in audit_resp.json()["items"]]
    assert "device.delete" in actions


async def test_rollout_abort_and_retry(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    d1 = Device(tenant_id=tenant.id, name="d1", pairing_state=PairingState.authorized)
    d2 = Device(tenant_id=tenant.id, name="d2", pairing_state=PairingState.authorized)
    db_session.add_all(
        [
            d1,
            d2,
            UpdateArtifact(
                tenant_id=tenant.id,
                version="9.9.9",
                target_board_rev="rev-c",
                storage_url="s3://a/9.9.9.img",
                checksum_sha256="e" * 64,
            ),
        ]
    )
    await db_session.commit()

    login_as(client, admin)
    artifacts = (await client.get("/update/artifacts")).json()
    resp = await client.post(
        "/update/rollouts", json={"artifact_id": artifacts["items"][0]["id"], "target": "all"}
    )
    assert resp.status_code == 202
    rollout_id = resp.json()["rollout_id"]

    # Simulate: d1 succeeded, d2 still pending -> abort revokes d2's command.
    from datetime import datetime, UTC

    from sqlalchemy import select

    from app.models.enums import DeviceRolloutStatus
    from app.models.update import UpdateRolloutDevice

    row_d1 = (
        await db_session.execute(
            select(UpdateRolloutDevice).where(
                UpdateRolloutDevice.rollout_id == __import__("uuid").UUID(rollout_id),
                UpdateRolloutDevice.device_id == d1.id,
            )
        )
    ).scalar_one()
    row_d1.status = DeviceRolloutStatus.succeeded
    row_d1.applied_at = datetime.now(UTC)
    await db_session.commit()

    resp = await client.post(f"/update/rollouts/{rollout_id}/abort")
    assert resp.status_code == 202
    assert resp.json()["aborted_devices"] == 1

    resp = await client.get("/update/rollouts")
    rollout = next(r for r in resp.json()["items"] if r["id"] == rollout_id)
    assert rollout["status"] == "failed"
    d2_row = next(d for d in rollout["devices"] if d["device_id"] == str(d2.id))
    assert d2_row["status"] == "failed"
    assert "aborted" in (d2_row["error"] or "")

    # Retry re-queues only the failed device.
    resp = await client.post(f"/update/rollouts/{rollout_id}/retry")
    assert resp.status_code == 202
    assert resp.json()["retried_devices"] == 1

    from app.models.pending_command import PendingCommand

    cmds = (
        await db_session.execute(
            select(PendingCommand).where(PendingCommand.device_id == d2.id)
        )
    ).scalars().all()
    assert len(cmds) == 1
    assert ":retry:" in cmds[0].command_id