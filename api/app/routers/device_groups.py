"""Static device groups: manual membership, used for deployment targeting
(rollouts can target a group) and later scoped access / per-group policies.
"""

from datetime import datetime, UTC
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.db.deps import get_db
from app.models.enums import UserRole
from app.models.device import Device
from app.models.device_group import DeviceGroup, DeviceGroupMember
from app.services import audit
from app.services.tenant_repo import TenantContext, TenantRepo

router = APIRouter(prefix="/device-groups", tags=["device-groups"])


class DeviceGroupIn(BaseModel):
    name: str


class DeviceGroupOut(BaseModel):
    id: UUID
    name: str
    device_ids: list[UUID]


class DeviceGroupListOut(BaseModel):
    items: list[DeviceGroupOut]


class DeviceGroupMembersIn(BaseModel):
    device_ids: list[UUID]


def _group_out(group: DeviceGroup) -> DeviceGroupOut:
    return DeviceGroupOut(
        id=group.id, name=group.name, device_ids=[m.device_id for m in group.members]
    )


@router.get("", response_model=DeviceGroupListOut)
async def list_groups(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    repo = TenantRepo(db, ctx)
    groups = (await db.execute(repo.scoped(DeviceGroup).order_by(DeviceGroup.name))).scalars().all()
    return DeviceGroupListOut(items=[_group_out(g) for g in groups])


@router.post("", response_model=DeviceGroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: DeviceGroupIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "name must not be empty")

    repo = TenantRepo(db, ctx)
    existing = (
        await db.execute(
            repo.scoped(DeviceGroup).where(DeviceGroup.name.ilike(name))
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "a group with this name already exists")

    group = repo.stamp_tenant(DeviceGroup(name=name))
    db.add(group)
    await audit.record(db, ctx, "device_group.create", payload={"name": name})
    await db.commit()
    await db.refresh(group)
    return _group_out(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.admin)),
):
    repo = TenantRepo(db, ctx)
    group = await repo.get_or_404(DeviceGroup, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")
    await audit.record(db, ctx, "device_group.delete", payload={"name": group.name})
    await db.delete(group)
    await db.commit()


@router.put("/{group_id}/members", response_model=DeviceGroupOut)
async def set_members(
    group_id: UUID,
    body: DeviceGroupMembersIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    """Replace the group's membership with the given device ids (must all
    belong to the tenant)."""
    repo = TenantRepo(db, ctx)
    group = await repo.get_or_404(DeviceGroup, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")

    devices = (
        (
            await db.execute(
                select(Device).where(
                    Device.id.in_(body.device_ids), Device.tenant_id == ctx.tenant_id
                )
            )
        )
        .scalars()
        .all()
    )
    if len(devices) != len(body.device_ids):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "one or more devices not found in this tenant"
        )

    await db.execute(
        DeviceGroupMember.__table__.delete().where(DeviceGroupMember.group_id == group.id)
    )
    now = datetime.now(UTC)
    for device in devices:
        db.add(DeviceGroupMember(group_id=group.id, device_id=device.id, added_at=now))
    await audit.record(
        db,
        ctx,
        "device_group.set_members",
        payload={"group": group.name, "count": len(devices)},
    )
    await db.commit()
    await db.refresh(group)
    return _group_out(group)