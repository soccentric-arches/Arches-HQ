from datetime import datetime, timedelta, UTC
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.config import get_settings
from app.db.deps import get_db
from app.models.device import Device
from app.models.device_credential import DeviceCredential
from app.models.enums import CommandKind, CredentialKind, PairingState, UserRole
from app.models.pending_command import PendingCommand
from app.schemas.common import Page
from app.schemas.device import (
    BulkProvisionCreate,
    BulkProvisionOut,
    DeviceCreate,
    DeviceCreateOut,
    DeviceListOut,
    DeviceOut,
    DeviceRename,
)
from app.services import audit
from app.services.device_scope import get_tenant_device_or_404
from app.services.device_store import device_db_path, export_device, import_device
from app.services.credentials import generate_token, hash_token
from app.services.tenant_repo import TenantContext, TenantRepo

router = APIRouter(prefix="/devices", tags=["devices"])


async def _create_device_with_pairing_token(
    db: AsyncSession, ctx: TenantContext, name: str
) -> tuple[Device, str]:
    repo = TenantRepo(db, ctx)
    device = repo.stamp_tenant(Device(name=name))
    db.add(device)
    await db.flush()

    settings = get_settings()
    raw_token = generate_token()
    pairing_expires_at = datetime.now(UTC) + timedelta(seconds=settings.pairing_token_ttl_seconds)
    db.add(
        DeviceCredential(
            device_id=device.id,
            kind=CredentialKind.pairing,
            token_hash=hash_token(raw_token),
            expires_at=pairing_expires_at,
        )
    )
    return device, raw_token


@router.get("", response_model=DeviceListOut)
async def list_devices(
    q: str | None = Query(default=None, description="filter by name substring"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    repo = TenantRepo(db, ctx)
    stmt = repo.scoped(Device)
    if q:
        # Search across every identity field the UI's global search exposes:
        # name, serial, IP, hostname.
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Device.name.ilike(like),
                Device.serial.ilike(like),
                Device.ip_address.ilike(like),
                Device.hostname.ilike(like),
            )
        )

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    # Online first, then most-recently-seen, then name -- IMPLEMENTATION_PLAN §1.3.
    stmt = stmt.order_by(
        Device.online.desc(), Device.last_seen_at.desc().nulls_last(), Device.name.asc()
    ).limit(limit).offset(offset)
    devices = (await db.execute(stmt)).scalars().all()

    return DeviceListOut(
        items=[DeviceOut.model_validate(d) for d in devices],
        page=Page(total=total, limit=limit, offset=offset),
    )


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    repo = TenantRepo(db, ctx)
    device = await repo.get_or_404(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    return DeviceOut.model_validate(device)


@router.post("", response_model=DeviceCreateOut, status_code=status.HTTP_201_CREATED)
async def create_device(
    body: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    repo = TenantRepo(db, ctx)
    device = repo.stamp_tenant(Device(name=body.name))
    db.add(device)
    await db.flush()

    settings = get_settings()
    raw_token = generate_token()
    pairing_expires_at = datetime.now(UTC) + timedelta(seconds=settings.pairing_token_ttl_seconds)
    db.add(
        DeviceCredential(
            device_id=device.id,
            kind=CredentialKind.pairing,
            token_hash=hash_token(raw_token),
            expires_at=pairing_expires_at,
        )
    )

    await audit.record(
        db, ctx, "device.create", target_device_id=device.id, payload={"name": device.name}
    )
    await db.commit()
    await db.refresh(device)
    return DeviceCreateOut(device=DeviceOut.model_validate(device), pairing_token=raw_token)


@router.post("/{device_id}/credential/rotate", response_model=DeviceCreateOut)
async def rotate_credential(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.admin)),
):
    """Issue a fresh single-use pairing token, revoking any prior credential.

    The device must re-pair with the new token; its existing live gateway
    connection (if any) is torn down because the gateway checks credential
    validity on every frame, not just at connect time (IMPLEMENTATION_PLAN §2.2).
    """
    repo = TenantRepo(db, ctx)
    device = await repo.get_or_404(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")

    now = datetime.now(UTC)
    await db.execute(
        DeviceCredential.__table__.update()
        .where(DeviceCredential.device_id == device.id, DeviceCredential.revoked_at.is_(None))
        .values(revoked_at=now)
    )

    settings = get_settings()
    raw_token = generate_token()
    db.add(
        DeviceCredential(
            device_id=device.id,
            kind=CredentialKind.pairing,
            token_hash=hash_token(raw_token),
            expires_at=now + timedelta(seconds=settings.pairing_token_ttl_seconds),
        )
    )
    device.pairing_state = PairingState.pending
    await audit.record(db, ctx, "device.credential.rotate", target_device_id=device.id)
    await db.commit()
    await db.refresh(device)
    return DeviceCreateOut(device=DeviceOut.model_validate(device), pairing_token=raw_token)


@router.post("/{device_id}/credential/revoke")
async def revoke_credential(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.admin)),
):
    repo = TenantRepo(db, ctx)
    device = await repo.get_or_404(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")

    now = datetime.now(UTC)
    await db.execute(
        DeviceCredential.__table__.update()
        .where(DeviceCredential.device_id == device.id, DeviceCredential.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    device.pairing_state = PairingState.revoked
    await audit.record(db, ctx, "device.credential.revoke", target_device_id=device.id)
    await db.commit()
    return {"ok": True}


@router.patch("/{device_id}", response_model=DeviceOut)
async def rename_device(
    device_id: UUID,
    body: DeviceRename,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "name must not be empty")

    repo = TenantRepo(db, ctx)
    device = await repo.get_or_404(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")

    device.name = name
    await audit.record(
        db, ctx, "device.rename", target_device_id=device.id, payload={"name": name}
    )
    await db.commit()
    await db.refresh(device)
    return DeviceOut.model_validate(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.admin)),
):
    """Decommission: remove the device and all of its data from HQ
    (credentials, telemetry, alarms, config). Irreversible; audited."""
    repo = TenantRepo(db, ctx)
    device = await repo.get_or_404(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")

    name = device.name
    await db.delete(device)
    await audit.record(db, ctx, "device.delete", payload={"name": name})
    await db.commit()
    return {"ok": True}


@router.post("/{device_id}/export")
async def export_device_data(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    """Mirror this device's rows into its per-device SQLite file under the
    storage root (storage/devices/<id>/device.sqlite). Idempotent.
    """
    repo = TenantRepo(db, ctx)
    device = await repo.get_or_404(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")

    path = await export_device(db, device, get_settings().storage_dir)
    await audit.record(db, ctx, "device.export", target_device_id=device.id)
    await db.commit()
    return {"ok": True, "path": str(path), "size_bytes": path.stat().st_size}


@router.get("/{device_id}/export/download")
async def download_device_export(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    repo = TenantRepo(db, ctx)
    device = await repo.get_or_404(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")

    path = device_db_path(get_settings().storage_dir, device.id)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no export yet -- run export first")
    return FileResponse(
        path,
        media_type="application/x-sqlite3",
        filename=f"device-{device.name}.sqlite",
    )


@router.post("/{device_id}/import")
async def import_device_data(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.admin)),
):
    """Restore rows from the device's SQLite file that are missing in
    the HQ database. Additive only; matched by primary key.
    """
    repo = TenantRepo(db, ctx)
    device = await repo.get_or_404(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")

    try:
        counts = await import_device(db, device, get_settings().storage_dir)
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "no export found -- run export first"
        ) from exc
    await audit.record(db, ctx, "device.import", target_device_id=device.id, payload=counts)
    await db.commit()
    return {"ok": True, "imported": counts}


@router.post("/bulk", response_model=BulkProvisionOut, status_code=status.HTTP_201_CREATED)
async def bulk_provision(
    body: BulkProvisionCreate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    """Pre-provision many devices at once (manufacturing / staging flow).

    Each name becomes a pending device with its own single-use pairing
    token -- hand the tokens to the devices' WebConfig HQ section and they
    enroll on first boot.
    """
    names = [n.strip() for n in body.names if n.strip()]
    if not names:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "no device names supplied")
    if len(set(names)) != len(names):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "duplicate names in request")
    if len(names) > 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "max 100 devices per batch")

    items = []
    for name in names:
        device, raw_token = await _create_device_with_pairing_token(db, ctx, name)
        items.append({"device": DeviceOut.model_validate(device), "pairing_token": raw_token})
    await audit.record(
        db, ctx, "device.bulk_provision", payload={"count": len(items), "names": names}
    )
    await db.commit()
    return BulkProvisionOut(items=items)


@router.post("/{device_id}/reboot", status_code=status.HTTP_202_ACCEPTED)
async def reboot_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    """Queues a Reboot command; agent-gateway delivers it on the device's
    next heartbeat (cross-process handoff, see PendingCommand).
    """
    await get_tenant_device_or_404(db, ctx, device_id)

    command_id = f"reboot:{uuid4()}"
    db.add(PendingCommand(device_id=device_id, command_id=command_id, kind=CommandKind.reboot))
    await audit.record(db, ctx, "device.reboot.request", target_device_id=device_id)
    await db.commit()
    return {"ok": True, "command_id": command_id}


@router.post("/{device_id}/shutdown", status_code=status.HTTP_202_ACCEPTED)
async def shutdown_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    """Queues a Shutdown command; agent-gateway delivers it on the device's
    next heartbeat (cross-process handoff, see PendingCommand).
    """
    await get_tenant_device_or_404(db, ctx, device_id)

    command_id = f"shutdown:{uuid4()}"
    db.add(PendingCommand(device_id=device_id, command_id=command_id, kind=CommandKind.shutdown))
    await audit.record(db, ctx, "device.shutdown.request", target_device_id=device_id)
    await db.commit()
    return {"ok": True, "command_id": command_id}


@router.post("/{device_id}/factory-reset", status_code=status.HTTP_202_ACCEPTED)
async def factory_reset_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.admin)),
):
    """Queues a FactoryReset command; agent-gateway delivers it on the
    device's next heartbeat (cross-process handoff, see PendingCommand).
    The device wipes local state and must re-pair afterwards.
    """
    await get_tenant_device_or_404(db, ctx, device_id)

    command_id = f"factory-reset:{uuid4()}"
    db.add(
        PendingCommand(device_id=device_id, command_id=command_id, kind=CommandKind.factory_reset)
    )
    await audit.record(db, ctx, "device.factory_reset.request", target_device_id=device_id)
    await db.commit()
    return {"ok": True, "command_id": command_id}


@router.post("/{device_id}/disable", response_model=DeviceOut)
async def disable_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.admin)),
):
    """Immediately revokes every live credential and marks the device
    disabled -- HQ refuses its connection even with a valid token.
    """
    repo = TenantRepo(db, ctx)
    device = await repo.get_or_404(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")

    now = datetime.now(UTC)
    await db.execute(
        DeviceCredential.__table__.update()
        .where(DeviceCredential.device_id == device.id, DeviceCredential.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    device.pairing_state = PairingState.disabled
    device.online = False
    await audit.record(db, ctx, "device.disable", target_device_id=device.id)
    await db.commit()
    await db.refresh(device)
    return DeviceOut.model_validate(device)
