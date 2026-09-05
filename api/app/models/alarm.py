import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Guid, TimestampTZ
from app.models.enums import AlarmState
from app.models.mixins import TenantScopedMixin, UUIDPKMixin


class AlarmRule(Base, TenantScopedMixin):
    """Operator-configured rule watching faults and/or telemetry. A fault
    existing does not automatically raise an alarm -- that mapping is
    explicit (IMPLEMENTATION_PLAN §3.3).
    """

    __tablename__ = "alarm_rule"

    name: Mapped[str]
    # {"kind": "fault_code", "severity": "critical"} or
    # {"kind": "telemetry_threshold", "metric": "cpu_temp", "op": ">", "value": 85,
    #  "for_seconds": 300}
    condition: Mapped[dict] = mapped_column(JSON)
    notify_channels: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Alarm(Base, UUIDPKMixin):
    __tablename__ = "alarm"

    alarm_rule_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("alarm_rule.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("device.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[AlarmState] = mapped_column(
        Enum(AlarmState, name="alarm_state"), default=AlarmState.active, index=True
    )
    triggered_at: Mapped[datetime] = mapped_column(TimestampTZ)
    acknowledged_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        Guid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)
    # Nullable: threshold-triggered alarms have no single originating fault.
    source_fault_id: Mapped[uuid.UUID | None] = mapped_column(
        Guid(), ForeignKey("fault.id", ondelete="SET NULL"), nullable=True
    )
