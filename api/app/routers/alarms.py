from datetime import datetime, UTC
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.db.deps import get_db
from app.models.alarm import Alarm, AlarmRule
from app.models.device import Device
from app.models.enums import AlarmState, UserRole
from app.schemas.alarm import AlarmListOut, AlarmOut, AlarmRuleCreate, AlarmRuleOut
from app.schemas.common import Page
from app.services import audit
from app.services.device_scope import get_tenant_device_or_404
from app.services.tenant_repo import TenantContext, TenantRepo

device_alarms_router = APIRouter(prefix="/devices/{device_id}/alarms", tags=["alarms"])
alarms_router = APIRouter(prefix="/alarms", tags=["alarms"])
alarm_rules_router = APIRouter(prefix="/alarm-rules", tags=["alarms"])


@device_alarms_router.get("", response_model=AlarmListOut)
async def list_device_alarms(
    device_id: UUID,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    await get_tenant_device_or_404(db, ctx, device_id)

    stmt = select(Alarm).where(Alarm.device_id == device_id)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Alarm.triggered_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()

    return AlarmListOut(
        items=[AlarmOut.model_validate(r) for r in rows],
        page=Page(total=total, limit=limit, offset=offset),
    )


async def _get_tenant_alarm_or_404(db: AsyncSession, ctx: TenantContext, alarm_id: UUID) -> Alarm:
    row = (
        await db.execute(
            select(Alarm).join(Device, Alarm.device_id == Device.id).where(
                Alarm.id == alarm_id, Device.tenant_id == ctx.tenant_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alarm not found")
    return row


@alarms_router.post("/{alarm_id}/acknowledge", response_model=AlarmOut)
async def acknowledge_alarm(
    alarm_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    alarm = await _get_tenant_alarm_or_404(db, ctx, alarm_id)
    alarm.state = AlarmState.acknowledged
    alarm.acknowledged_at = datetime.now(UTC)
    alarm.acknowledged_by = ctx.user_id
    await audit.record(db, ctx, "alarm.acknowledge", target_device_id=alarm.device_id)
    await db.commit()
    await db.refresh(alarm)
    return AlarmOut.model_validate(alarm)


@alarms_router.post("/{alarm_id}/resolve", response_model=AlarmOut)
async def resolve_alarm(
    alarm_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    alarm = await _get_tenant_alarm_or_404(db, ctx, alarm_id)
    alarm.state = AlarmState.resolved
    alarm.resolved_at = datetime.now(UTC)
    await audit.record(db, ctx, "alarm.resolve", target_device_id=alarm.device_id)
    await db.commit()
    await db.refresh(alarm)
    return AlarmOut.model_validate(alarm)


@alarm_rules_router.get("", response_model=list[AlarmRuleOut])
async def list_alarm_rules(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    repo = TenantRepo(db, ctx)
    rows = (await db.execute(repo.scoped(AlarmRule).order_by(AlarmRule.name))).scalars().all()
    return [AlarmRuleOut.model_validate(r) for r in rows]


@alarm_rules_router.post("", response_model=AlarmRuleOut, status_code=status.HTTP_201_CREATED)
async def create_alarm_rule(
    body: AlarmRuleCreate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    repo = TenantRepo(db, ctx)
    rule = repo.stamp_tenant(
        AlarmRule(
            name=body.name,
            condition=body.condition,
            notify_channels=body.notify_channels,
            enabled=body.enabled,
        )
    )
    db.add(rule)
    await audit.record(db, ctx, "alarm_rule.create", payload={"name": body.name})
    await db.commit()
    await db.refresh(rule)
    return AlarmRuleOut.model_validate(rule)
