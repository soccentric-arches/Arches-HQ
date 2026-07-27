from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.db.deps import get_db
from app.models.device import Device
from app.models.enums import UserRole
from app.schemas.common import Page
from app.schemas.device import DeviceCreate, DeviceCreateOut, DeviceListOut, DeviceOut
from app.services import audit
from app.services.tenant_repo import TenantContext, TenantRepo

router = APIRouter(prefix="/devices", tags=["devices"])


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
        stmt = stmt.where(Device.name.ilike(f"%{q}%"))

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
    await audit.record(
        db, ctx, "device.create", target_device_id=device.id, payload={"name": device.name}
    )
    await db.commit()
    await db.refresh(device)
    return DeviceCreateOut(device=DeviceOut.model_validate(device), pairing_token=None)
