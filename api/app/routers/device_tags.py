"""Freeform device tags: add/remove labels on a device; tags are used by
the device page and (later) list filters."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.db.deps import get_db
from app.models.device_tag import DeviceTag
from app.models.enums import UserRole
from app.services import audit
from app.services.device_scope import get_tenant_device_or_404
from app.services.tenant_repo import TenantContext

router = APIRouter(prefix="/devices/{device_id}/tags", tags=["device-tags"])


class DeviceTagsIn(BaseModel):
    tags: list[str]


class DeviceTagsOut(BaseModel):
    tags: list[str]


def _clean(tags: list[str]) -> list[str]:
    cleaned = sorted({t.strip() for t in tags if t.strip()})
    if len(cleaned) > 20:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "max 20 tags per device")
    for t in cleaned:
        if len(t) > 64:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "tag too long (max 64)")
    return cleaned


@router.get("")
async def get_tags(
    device_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    await get_tenant_device_or_404(db, ctx, device_id)
    rows = (
        (
            await db.execute(
                select(DeviceTag)
                .where(DeviceTag.device_id == device_id)
                .order_by(DeviceTag.tag)
            )
        )
        .scalars()
        .all()
    )
    return DeviceTagsOut(tags=[r.tag for r in rows])


@router.put("")
async def set_tags(
    device_id: UUID,
    body: DeviceTagsIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    """Replace the device's tag set (idempotent full-state write)."""
    device = await get_tenant_device_or_404(db, ctx, device_id)
    cleaned = _clean(body.tags)

    existing = (
        (
            await db.execute(select(DeviceTag).where(DeviceTag.device_id == device_id))
        )
        .scalars()
        .all()
    )
    for row in existing:
        if row.tag not in cleaned:
            await db.delete(row)
    have = {r.tag for r in existing}
    for tag in cleaned:
        if tag not in have:
            db.add(DeviceTag(tenant_id=ctx.tenant_id, device_id=device_id, tag=tag))
    await audit.record(
        db, ctx, "device.tags.set", target_device_id=device.id, payload={"tags": cleaned}
    )
    await db.commit()
    return DeviceTagsOut(tags=cleaned)