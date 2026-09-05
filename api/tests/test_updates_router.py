from app.models.device import Device
from app.models.enums import PairingState, RolloutStatus, UserRole
from app.models.update import UpdateArtifact
from tests.factories import login_as, make_tenant, make_user


async def test_artifact_create_and_list(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    await db_session.commit()

    login_as(client, admin)
    resp = await client.post(
        "/update/artifacts",
        json={
            "version": "2.1.0",
            "target_board_rev": "rev-c",
            "storage_url": "s3://artifacts/2.1.0.img",
            "checksum_sha256": "a" * 64,
        },
    )
    assert resp.status_code == 201

    resp = await client.get("/update/artifacts")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["version"] == "2.1.0"


async def test_artifact_create_requires_admin(client, db_session):
    tenant = await make_tenant(db_session)
    operator = await make_user(db_session, tenant, UserRole.operator)
    await db_session.commit()

    login_as(client, operator)
    resp = await client.post(
        "/update/artifacts",
        json={
            "version": "1.0.0",
            "target_board_rev": "rev-c",
            "storage_url": "s3://x",
            "checksum_sha256": "b" * 64,
        },
    )
    assert resp.status_code == 403


async def test_rollout_creates_apply_update_commands(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    await db_session.commit()
    d1 = Device(tenant_id=tenant.id, name="d1", pairing_state=PairingState.authorized)
    d2 = Device(tenant_id=tenant.id, name="d2", pairing_state=PairingState.authorized)
    db_session.add_all([d1, d2, UpdateArtifact(
        tenant_id=tenant.id,
        version="3.0.0",
        target_board_rev="rev-c",
        storage_url="s3://artifacts/3.0.0.img",
        checksum_sha256="c" * 64,
    )])
    await db_session.commit()

    login_as(client, admin)
    resp = await client.post(
        "/update/rollouts",
        json={"artifact_id": None, "target": "all", "device_ids": []},
    )
    # artifact_id None -> 422
    assert resp.status_code == 422

    artifacts = (await client.get("/update/artifacts")).json()
    resp = await client.post(
        "/update/rollouts",
        json={"artifact_id": artifacts["items"][0]["id"], "target": "all"},
    )
    assert resp.status_code == 202
    assert resp.json()["device_count"] == 2

    # Each targeted device got an apply_update pending command.
    from sqlalchemy import select
    from app.models.pending_command import PendingCommand as PC
    result = await db_session.execute(select(PC))
    cmds = result.scalars().all()
    assert len(cmds) == 2
    assert all(c.kind.value == "apply_update" for c in cmds)
    assert all(c.command_id.startswith("update:") for c in cmds)

    # Rollout visible with per-device rows.
    resp = await client.get("/update/rollouts")
    assert resp.status_code == 200
    rollout = resp.json()["items"][0]
    assert rollout["status"] == RolloutStatus.in_progress.value
    assert len(rollout["devices"]) == 2


async def test_rollout_specific_devices_only(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    await db_session.commit()
    d1 = Device(tenant_id=tenant.id, name="d1", pairing_state=PairingState.authorized)
    d2 = Device(tenant_id=tenant.id, name="d2", pairing_state=PairingState.authorized)
    db_session.add_all([d1, d2, UpdateArtifact(
        tenant_id=tenant.id,
        version="3.1.0",
        target_board_rev="rev-c",
        storage_url="s3://artifacts/3.1.0.img",
        checksum_sha256="d" * 64,
    )])
    await db_session.commit()

    login_as(client, admin)
    resp = await client.post(
        "/update/rollouts",
        json={"artifact_id": None, "target": "specific_devices", "device_ids": []},
    )
    assert resp.status_code == 422  # empty device_ids

    artifacts = (await client.get("/update/artifacts")).json()
    resp = await client.post(
        "/update/rollouts",
        json={
            "artifact_id": artifacts["items"][0]["id"],
            "target": "specific_devices",
            "device_ids": [str(d1.id)],
        },
    )
    assert resp.status_code == 202
    assert resp.json()["device_count"] == 1
