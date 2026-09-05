import uuid
from datetime import datetime, UTC

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Guid, TimestampTZ


def utcnow() -> datetime:
    return datetime.now(UTC)


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Guid(), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, default=utcnow)


class TenantScopedMixin(UUIDPKMixin, TimestampMixin):
    """Every tenant-owned table gets `tenant_id` this way -- never ad hoc.

    IMPLEMENTATION_PLAN §6: "the single most important invariant in the
    whole system." Query-layer enforcement lives in
    app/services/tenant_repo.py, not here -- this mixin only guarantees the
    column exists and is indexed/foreign-keyed.
    """

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("tenant.id", ondelete="CASCADE"), index=True
    )
