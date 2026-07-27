from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.db.deps import get_db
from app.models.enums import UserRole
from app.models.telemetry import TelemetrySample
from app.services.device_scope import get_tenant_device_or_404
from app.services.tenant_repo import TenantContext

router = APIRouter(prefix="/devices/{device_id}/telemetry", tags=["telemetry"])

# location is reported via the same TelemetrySample table but isn't a
# chartable numeric metric -- excluded from the general series response.
_EXCLUDED_METRICS = {"location"}


@router.get("")
async def get_telemetry(
    device_id: UUID,
    metric: str | None = Query(default=None),
    points_per_metric: int = Query(default=200, le=2000),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role(UserRole.viewer)),
):
    await get_tenant_device_or_404(db, ctx, device_id)

    stmt = select(TelemetrySample).where(TelemetrySample.device_id == device_id)
    if metric:
        stmt = stmt.where(TelemetrySample.metric == metric)
    else:
        stmt = stmt.where(TelemetrySample.metric.not_in(_EXCLUDED_METRICS))
    stmt = stmt.order_by(TelemetrySample.recorded_at.desc()).limit(points_per_metric * 20)

    samples = (await db.execute(stmt)).scalars().all()

    series: dict[str, list[dict]] = {}
    for sample in samples:
        bucket = series.setdefault(sample.metric, [])
        if len(bucket) < points_per_metric:
            bucket.append({"recorded_at": sample.recorded_at.isoformat(), "value": sample.value})

    for bucket in series.values():
        bucket.reverse()  # oldest -> newest for chart rendering
    return series
