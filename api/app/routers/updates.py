"""OTA updates: artifacts (versioned images) and rollouts (delivering an
artifact to devices). Creating a rollout enqueues an ApplyUpdate pending
command per targeted device; agent-gateway delivers it on the device's next
heartbeat and the CommandAck (command_id "update:{rollout_id}:...") flips
the per-device rollout status -- see gateway/handlers.py.
"""

from datetime import datetime, UTC
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.db.deps import get_db
from app.models.device import Device
from app.models.device_group import DeviceGroup, DeviceGroupMember
from app.models.enums import CommandKind, PairingState, RolloutStatus, RolloutTarget, UserRole
from app.models.pending_command import PendingCommand
from app.models.update import UpdateArtifact, UpdateRollout, UpdateRolloutDevice
from app.schemas.common import Page
from app.services import audit
from app.services.storage import presigned_download_url
from app.services.tenant_repo import TenantContext, TenantRepo

router = APIRouter(prefix="/update", tags=["updates"])

ROLLOUT_PAGE_SIZE = 50


# ---- schemas ----


class UpdateArtifactIn(BaseModel):
    version: str
    target_board_rev: str
    storage_url: str
    checksum_sha256: str


class UpdateArtifactOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    version: str
    target_board_rev: str
    storage_url: str
    checksum_sha256: str


class UpdateArtifactListOut(BaseModel):
    items: list[UpdateArtifactOut]
    page: Page


class UpdateRolloutDeviceOut(BaseModel):
    model_config = {"from_attributes": True}

    device_id: UUID
    status: str
    applied_at: datetime | None
    error: str | None


class UpdateRolloutOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    artifact_id: UUID
    artifact_version: str
    target: RolloutTarget
    status: RolloutStatus
    started_at: datetime | None
    completed_at: datetime | None
    devices: list[UpdateRolloutDeviceOut]


class UpdateRolloutListOut(BaseModel):
    items: list[UpdateRolloutOut]
    page: Page


class UpdateRolloutIn(BaseModel):
    artifact_id: UUID
    target: RolloutTarget
    device_ids: list[UUID] = []
    device_group_id: UUID | None = None


# ---- artifacts ----


@router.get("/artifacts", response_model=UpdateArtifactListOut)
async def list_artifacts(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    repo = TenantRepo(db, ctx)
    stmt = repo.scoped(UpdateArtifact)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (await db.execute(stmt.order_by(UpdateArtifact.version.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return UpdateArtifactListOut(
        items=[UpdateArtifactOut.model_validate(r) for r in rows],
        page=Page(total=total, limit=limit, offset=offset),
    )


@router.post("/artifacts", response_model=UpdateArtifactOut, status_code=status.HTTP_201_CREATED)
async def create_artifact(
    body: UpdateArtifactIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.admin)),
):
    repo = TenantRepo(db, ctx)
    artifact = repo.stamp_tenant(UpdateArtifact(**body.model_dump()))
    db.add(artifact)
    await audit.record(db, ctx, "update.artifact.create", payload={"version": body.version})
    await db.commit()
    await db.refresh(artifact)
    return UpdateArtifactOut.model_validate(artifact)


# ---- rollouts ----


async def _rollout_out(db: AsyncSession, rollout: UpdateRollout) -> UpdateRolloutOut:
    artifact = await db.get(UpdateArtifact, rollout.artifact_id)
    rows = (
        await db.execute(
            select(UpdateRolloutDevice).where(UpdateRolloutDevice.rollout_id == rollout.id)
        )
    ).scalars().all()
    return UpdateRolloutOut(
        id=rollout.id,
        artifact_id=rollout.artifact_id,
        artifact_version=artifact.version if artifact else "?",
        target=rollout.target,
        status=rollout.status,
        started_at=rollout.started_at,
        completed_at=rollout.completed_at,
        devices=[
            UpdateRolloutDeviceOut(
                device_id=r.device_id,
                status=r.status.value if hasattr(r.status, "value") else str(r.status),
                applied_at=r.applied_at,
                error=r.error,
            )
            for r in rows
        ],
    )


@router.get("/rollouts", response_model=UpdateRolloutListOut)
async def list_rollouts(
    limit: int = Query(default=ROLLOUT_PAGE_SIZE, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    # UpdateRollout itself is not tenant-scoped; scope through its device
    # rows back to the tenant's devices.
    tenant_device_ids = select(Device.id).where(Device.tenant_id == ctx.tenant_id).subquery()
    stmt = select(UpdateRollout).where(
        UpdateRollout.id.in_(
            select(UpdateRolloutDevice.rollout_id).where(
                UpdateRolloutDevice.device_id.in_(tenant_device_ids)
            )
        )
    )
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rollouts = (
        (await db.execute(stmt.order_by(UpdateRollout.id.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    items = [await _rollout_out(db, r) for r in rollouts]
    return UpdateRolloutListOut(items=items, page=Page(total=total, limit=limit, offset=offset))


@router.post("/rollouts", status_code=status.HTTP_202_ACCEPTED)
async def create_rollout(
    body: UpdateRolloutIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.admin)),
):
    repo = TenantRepo(db, ctx)
    artifact = await repo.get_or_404(UpdateArtifact, body.artifact_id)
    if artifact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "artifact not found")

    # Resolve the target set (tenant-scoped, authorized devices only).
    device_stmt = repo.scoped(Device).where(Device.pairing_state == PairingState.authorized)
    if body.target == RolloutTarget.device_group:
        if body.device_group_id is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "device_group_id required for device_group"
            )
        group = await repo.get_or_404(DeviceGroup, body.device_group_id)
        if group is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")
        members = (
            await db.execute(
                select(DeviceGroupMember.device_id).where(
                    DeviceGroupMember.group_id == body.device_group_id
                )
            )
        ).scalars().all()
        if not members:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "target group is empty")
        device_stmt = device_stmt.where(Device.id.in_(members))
    if body.target == RolloutTarget.specific_devices:
        if not body.device_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "device_ids required for specific_devices"
            )
        device_stmt = device_stmt.where(Device.id.in_(body.device_ids))
    devices = (await db.execute(device_stmt)).scalars().all()
    if not devices:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "no eligible devices to target")

    rollout = UpdateRollout(
        artifact_id=artifact.id,
        target=body.target,
        target_selector=(
            {"device_ids": [str(d.id) for d in devices]}
            if body.target == RolloutTarget.specific_devices
            else (
                {"group_id": str(body.device_group_id)}
                if body.target == RolloutTarget.device_group
                else {}
            )
        ),
        status=RolloutStatus.in_progress,
        started_at=datetime.now(UTC),
    )
    db.add(rollout)
    await db.flush()

    download_url = presigned_download_url(artifact.storage_url)
    for device in devices:
        db.add(
            UpdateRolloutDevice(
                rollout_id=rollout.id,
                device_id=device.id,
            )
        )
        # Per-device command_id: globally unique, and the ack handler only
        # parses the rollout segment ("update:{rollout_id}:...").
        db.add(
            PendingCommand(
                device_id=device.id,
                command_id=f"update:{rollout.id}:{device.id}",
                kind=CommandKind.apply_update,
                payload={
                    "artifact_id": str(artifact.id),
                    "artifact_download_url": download_url,
                    "checksum_sha256": artifact.checksum_sha256,
                },
            )
        )

    await audit.record(
        db,
        ctx,
        "update.rollout.create",
        payload={
            "rollout_id": str(rollout.id),
            "artifact_version": artifact.version,
            "device_count": len(devices),
        },
    )
    await db.commit()
    return {"ok": True, "rollout_id": str(rollout.id), "device_count": len(devices)}

@router.post("/rollouts/{rollout_id}/abort", status_code=status.HTTP_202_ACCEPTED)
async def abort_rollout(
    rollout_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.admin)),
):
    """Abort an in-flight rollout: revoke every not-yet-delivered command and
    mark the remaining devices failed (delivered ones keep their outcome)."""
    stmt = select(UpdateRollout).where(UpdateRollout.id == rollout_id)
    rollout = (await db.execute(stmt)).scalar_one_or_none()
    if rollout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rollout not found")

    # Tenant check through the device rows.
    tenant_devices = (
        await db.execute(
            select(UpdateRolloutDevice.device_id).where(UpdateRolloutDevice.rollout_id == rollout.id)
        )
    ).scalars().all()
    owned = (
        await db.execute(select(Device.id).where(Device.id.in_(tenant_devices), Device.tenant_id == ctx.tenant_id))
    ).scalars().all()
    if not owned:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rollout not found")

    rows = (
        await db.execute(
            select(UpdateRolloutDevice).where(UpdateRolloutDevice.rollout_id == rollout.id)
        )
    ).scalars().all()
    pending_ids = [r.device_id for r in rows if r.status == DeviceRolloutStatus.pending]

    # Revoke undelivered commands for those devices.
    for device_id in pending_ids:
        await db.execute(
            PendingCommand.__table__.delete().where(
                PendingCommand.device_id == device_id,
                PendingCommand.command_id.like(f"update:{rollout.id}:%"),
                PendingCommand.delivered_at.is_(None),
            )
        )
        row = next(r for r in rows if r.device_id == device_id)
        row.status = DeviceRolloutStatus.failed
        row.error = "aborted by operator"

    remaining = [r for r in rows if r.status not in (DeviceRolloutStatus.succeeded, DeviceRolloutStatus.failed)]
    if not remaining:
        rollout.status = RolloutStatus.failed
        rollout.completed_at = datetime.now(UTC)

    await audit.record(
        db, ctx, "update.rollout.abort", payload={"rollout_id": str(rollout.id), "aborted_devices": len(pending_ids)}
    )
    await db.commit()
    return {"ok": True, "aborted_devices": len(pending_ids)}


@router.post("/rollouts/{rollout_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_rollout(
    rollout_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.admin)),
):
    """Re-queue the update for every failed device of a rollout."""
    rollout = (await db.execute(select(UpdateRollout).where(UpdateRollout.id == rollout_id))).scalar_one_or_none()
    if rollout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rollout not found")
    artifact = await db.get(UpdateArtifact, rollout.artifact_id)

    rows = (
        await db.execute(
            select(UpdateRolloutDevice).where(UpdateRolloutDevice.rollout_id == rollout.id)
        )
    ).scalars().all()
    failed_ids = [r.device_id for r in rows if r.status == DeviceRolloutStatus.failed]
    if not failed_ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "no failed devices to retry")

    download_url = presigned_download_url(artifact.storage_url)
    for device_id in failed_ids:
        row = next(r for r in rows if r.device_id == device_id)
        row.status = DeviceRolloutStatus.pending
        row.error = None
        db.add(
            PendingCommand(
                device_id=device_id,
                command_id=f"update:{rollout.id}:{device_id}:retry:{uuid4()}",
                kind=CommandKind.apply_update,
                payload={
                    "artifact_id": str(artifact.id),
                    "artifact_download_url": download_url,
                    "checksum_sha256": artifact.checksum_sha256,
                },
            )
        )
    rollout.status = RolloutStatus.in_progress
    rollout.completed_at = None

    await audit.record(
        db, ctx, "update.rollout.retry", payload={"rollout_id": str(rollout.id), "retried_devices": len(failed_ids)}
    )
    await db.commit()
    return {"ok": True, "retried_devices": len(failed_ids)}
