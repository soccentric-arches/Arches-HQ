"""Desired device configuration, per section (system / time / network /
security). HQ stores the operator's intent; the device agent applies it
device-side and is notified via an ApplyConfig pending command.
"""

from datetime import datetime, UTC
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.db.deps import get_db
from app.models.device_config import CONFIG_SECTIONS, DeviceConfig
from app.models.enums import CommandKind, UserRole
from app.models.pending_command import PendingCommand
from app.schemas.device import DeviceConfigIn, DeviceConfigOut
from app.services import audit
from app.services.device_scope import get_tenant_device_or_404
from app.services.tenant_repo import TenantContext

router = APIRouter(prefix="/devices/{device_id}/config", tags=["device-config"])


@router.get("/{section}", response_model=DeviceConfigOut)
async def get_config(
    device_id: UUID,
    section: str,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    if section not in CONFIG_SECTIONS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown config section")
    await get_tenant_device_or_404(db, ctx, device_id)

    row = (
        await db.execute(
            select(DeviceConfig).where(
                DeviceConfig.device_id == device_id, DeviceConfig.section == section
            )
        )
    ).scalar_one_or_none()
    if row is None:
        # Unset sections read as empty desired state, not 404 -- the UI
        # forms start blank.
        return DeviceConfigOut(
            device_id=device_id, section=section, config={}, updated_at=datetime.now(UTC)
        )
    return DeviceConfigOut.model_validate(row)


@router.put("/{section}", response_model=DeviceConfigOut)
async def put_config(
    device_id: UUID,
    section: str,
    body: DeviceConfigIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    if section not in CONFIG_SECTIONS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown config section")
    await get_tenant_device_or_404(db, ctx, device_id)

    row = (
        await db.execute(
            select(DeviceConfig).where(
                DeviceConfig.device_id == device_id, DeviceConfig.section == section
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = DeviceConfig(device_id=device_id, section=section)
        db.add(row)
    row.config = body.config
    row.updated_at = datetime.now(UTC)

    # Notify the device that this section changed; it applies the new
    # desired state device-side (Arches-Configuration owns that half).
    command_id = f"config:{device_id}:{section}:{row.updated_at.timestamp():.0f}"
    db.add(
        PendingCommand(
            device_id=device_id,
            command_id=command_id,
            kind=CommandKind.apply_config,
            payload={"section": section},
        )
    )
    await audit.record(
        db,
        ctx,
        "device.config.update",
        target_device_id=device_id,
        payload={"section": section},
    )
    await db.commit()
    await db.refresh(row)
    return DeviceConfigOut.model_validate(row)