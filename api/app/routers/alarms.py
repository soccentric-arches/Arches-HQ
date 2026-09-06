from datetime import datetime, UTC
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.db.deps import get_db
from app.models.alarm import Alarm, AlarmRule
from app.models.device import Device
from app.models.device_alarm import DeviceAlarm
from app.models.enums import AlarmState, UserRole
from app.schemas.alarm import AlarmOut, AlarmRuleCreate, AlarmRuleOut
from app.schemas.alarm_history import AlarmHistoryListOut
from app.schemas.common import Page
from app.schemas.device_alarm import (
    ActiveAlarmListOut,
    ActiveAlarmOut,
    DeviceAlarmIn,
    DeviceAlarmListOut,
    DeviceAlarmOut,
)
from app.services import audit
from app.services.device_scope import get_tenant_device_or_404
from app.services.tenant_repo import TenantContext, TenantRepo

device_alarms_router = APIRouter(prefix="/devices/{device_id}/alarms", tags=["alarms"])
alarms_router = APIRouter(prefix="/alarms", tags=["alarms"])
alarm_rules_router = APIRouter(prefix="/alarm-rules", tags=["alarms"])

# Alarm identity: 32-bit packed code (device-reported alarms, R3 ingest path).
#
# SOURCE OF TRUTH: Arches-Instrumentation/catalog/alarms.yaml (header) and
# Arches-Instrumentation/REQ.md section 8. The layout is marked *locked* there:
# the device's alarms daemon generates its C++ header from that catalog, so HQ
# decodes against it rather than the other way round.
#
#   [31:28]  domain  (4 bits)   hardware / software / network / application / fault
#   [27:20]  module  (8 bits)   which daemon or subsystem (256)
#   [19:16]  type    (4 bits)   X.733 category: equipment, communications,
#                               processing-error, quality-of-service, environmental
#   [15:0]   index   (16 bits)  alarm within that module (65536)
#
# Worked example from REQ.md section 8: the catalog spelling 0x1_04_1_0007
# packs to 0x10410007 and reads as hardware / Hardware daemon / equipment /
# alarm 7 -- i.e. (domain=1, module=4, type=1, index=7).
#
# SEVERITY IS NOT IN THE CODE. It is a separate field on the device's
# AlarmEvent, because the same alarm can be raised at different severities and
# because severity changes over an alarm's life (X.733 severity-change events).
#
# This module previously unpacked the word as four equal bytes and called the
# low byte "severity". That is wrong at every offset, not merely shifted: the
# byte boundaries fall inside the domain and module fields, so 0x10410007 came
# out as (16, 65, 0, 7) instead of (1, 4, 1, 7). See Task.md C-03/C-04.

_DOMAIN_SHIFT, _DOMAIN_MASK = 28, 0xF
_MODULE_SHIFT, _MODULE_MASK = 20, 0xFF
_TYPE_SHIFT, _TYPE_MASK = 16, 0xF
_INDEX_MASK = 0xFFFF


def _decode_alarm_code(code: int) -> tuple[int, int, int, int]:
    """Unpack a packed alarm code into ``(domain, module, alarm_type, index)``.

    Severity is deliberately absent -- it travels as its own field, not inside
    the code. See the layout note above.
    """
    return (
        (code >> _DOMAIN_SHIFT) & _DOMAIN_MASK,
        (code >> _MODULE_SHIFT) & _MODULE_MASK,
        (code >> _TYPE_SHIFT) & _TYPE_MASK,
        code & _INDEX_MASK,
    )


def _encode_alarm_code(domain: int, module: int, alarm_type: int, index: int) -> int:
    """Pack ``(domain, module, alarm_type, index)`` back into a 32-bit code.

    Present so the decode can be round-trip tested against the locked layout
    rather than only spot-checked.
    """
    return (
        ((domain & _DOMAIN_MASK) << _DOMAIN_SHIFT)
        | ((module & _MODULE_MASK) << _MODULE_SHIFT)
        | ((alarm_type & _TYPE_MASK) << _TYPE_SHIFT)
        | (index & _INDEX_MASK)
    )


@device_alarms_router.get("", response_model=DeviceAlarmListOut)
async def list_device_alarms(
    device_id: UUID,
    since: datetime | None = Query(
        default=None, description="only alarms triggered after this instant"
    ),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    """List device-reported alarms from the ``alarms`` table (R3).

    Returns rows for the tenant's device, newest first, with the decoded
    4-byte alarm scheme fields.
    """
    await get_tenant_device_or_404(db, ctx, device_id)

    stmt = select(DeviceAlarm).where(DeviceAlarm.device_id == device_id)
    if since:
        stmt = stmt.where(DeviceAlarm.triggered_at >= since)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(DeviceAlarm.triggered_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()

    return DeviceAlarmListOut(
        items=[DeviceAlarmOut.model_validate(r) for r in rows],
        page=Page(total=total, limit=limit, offset=offset),
    )


@device_alarms_router.post(
    "", response_model=DeviceAlarmOut, status_code=status.HTTP_201_CREATED
)
async def ingest_device_alarm(
    device_id: UUID,
    body: DeviceAlarmIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    """Ingest a device-reported 4-byte alarm into the ``alarms`` table (R3).

    The device must belong to the caller's tenant (scoped via the parent
    device). ``alarm_code`` is a hex string (e.g. ``"0x01020304"``) decoded
    into domain / module / alarm_type / index using the locked layout
    documented at the top of this module. Severity is carried as its own
    field on the payload, not extracted from the code. The row is created in the ``active``
    state. ``triggered_at`` is the device-side timestamp, stored verbatim.
    """
    await get_tenant_device_or_404(db, ctx, device_id)

    try:
        code = int(body.alarm_code, 16)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "alarm_code must be a hex string e.g. '0x10410007'",
        ) from exc
    if code < 0 or code > 0xFFFFFFFF:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "alarm_code must fit in 4 bytes (0x00000000..0xffffffff)",
        )

    domain, module, alarm_type, alarm_index = _decode_alarm_code(code)

    alarm = DeviceAlarm(
        device_id=device_id,
        domain=domain,
        module=module,
        alarm_type=alarm_type,
        alarm_index=alarm_index,
        severity=body.severity,
        alarm_code=code,
        state=AlarmState.active,
        triggered_at=body.triggered_at,
    )
    db.add(alarm)
    await db.flush()
    await audit.record(
        db,
        ctx,
        "alarm.ingest",
        target_device_id=device_id,
        payload={"alarm_code": body.alarm_code},
    )
    await db.commit()
    await db.refresh(alarm)
    return DeviceAlarmOut.model_validate(alarm)


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


@alarms_router.get("", response_model=AlarmHistoryListOut)
async def list_rule_alarms(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    """Rule-based alarm history (the pre-existing `alarm` table), newest
    first, with device names for the Alerts page."""
    device_alias = Device
    stmt = (
        select(Alarm, device_alias.name)
        .join(device_alias, Alarm.device_id == device_alias.id)
        .where(device_alias.tenant_id == ctx.tenant_id)
        .order_by(Alarm.triggered_at.desc())
    )
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.limit(limit).offset(offset))).all()
    items = []
    for alarm, device_name in rows:
        out = AlarmOut.model_validate(alarm)
        items.append({"alarm": out, "device_name": device_name})
    return AlarmHistoryListOut(items=items, page=Page(total=total, limit=limit, offset=offset))


@alarms_router.get("/active", response_model=ActiveAlarmListOut)
async def list_active_alarms(
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    """Fleet-wide active device alarms, newest first, with device names.

    Powers the top-bar alert bell (count + dropdown) and the overview page.
    """
    stmt = (
        select(DeviceAlarm, Device.name)
        .join(Device, DeviceAlarm.device_id == Device.id)
        .where(
            DeviceAlarm.state == AlarmState.active,
            Device.tenant_id == ctx.tenant_id,
        )
        .order_by(DeviceAlarm.triggered_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    total = (
        await db.execute(
            select(func.count())
            .select_from(DeviceAlarm)
            .join(Device, DeviceAlarm.device_id == Device.id)
            .where(DeviceAlarm.state == AlarmState.active, Device.tenant_id == ctx.tenant_id)
        )
    ).scalar_one()

    items = [
        ActiveAlarmOut(
            id=a.id,
            device_id=a.device_id,
            device_name=name,
            domain=a.domain,
            module=a.module,
            alarm_type=a.alarm_type,
            alarm_index=a.alarm_index,
            severity=a.severity,
            alarm_code=a.alarm_code,
            state=a.state,
            triggered_at=a.triggered_at,
        )
        for a, name in rows
    ]
    return ActiveAlarmListOut(count=total, items=items)


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


@device_alarms_router.post("/{alarm_id}/clear", response_model=DeviceAlarmOut)
async def clear_device_alarm(
    device_id: UUID,
    alarm_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.operator)),
):
    """Device-scoped "clear" verb for a device-reported alarm (R3).

    ``clear`` is semantically identical to ``resolve``: the alarm's state
    transitions ``active -> resolved`` and ``resolved_at`` is stamped. There
    is no separate ``cleared`` state -- the existing ``AlarmState`` enum has
    only ``active``/``acknowledged``/``resolved``, and ``clear`` reuses
    ``resolved`` (F5 equivalence). The alarm must belong to the device in
    the path and to the caller's tenant.
    """
    await get_tenant_device_or_404(db, ctx, device_id)
    row = (
        await db.execute(
            select(DeviceAlarm).where(
                DeviceAlarm.id == alarm_id, DeviceAlarm.device_id == device_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alarm not found")
    row.state = AlarmState.resolved
    row.resolved_at = datetime.now(UTC)
    await audit.record(db, ctx, "alarm.clear", target_device_id=device_id)
    await db.commit()
    await db.refresh(row)
    return DeviceAlarmOut.model_validate(row)


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
