import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
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
    condition: Mapped[dict] = mapped_column(JSONB)
    notify_channels: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Alarm(Base, UUIDPKMixin):
    __tablename__ = "alarm"

    # Nullable: device-reported alarms (R3 ingest path) have no rule, only the
    # 4-byte alarm code. Rule-based alarms still carry the originating rule.
    alarm_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alarm_rule.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("device.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[AlarmState] = mapped_column(
        Enum(AlarmState, name="alarm_state"), default=AlarmState.active, index=True
    )
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Nullable: threshold-triggered alarms have no single originating fault.
    source_fault_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fault.id", ondelete="SET NULL"), nullable=True
    )

    # 4-byte alarm scheme fields for device-reported alarms (R3 ingest path).
    # All nullable so existing rule-based alarms still insert cleanly.
    # Byte order of `alarm_code` (big-endian uint32, byte 0 = most significant):
    #   byte 0 = major_id, byte 1 = sub_section,
    #   byte 2 = fault_type, byte 3 = severity.
    major_id: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sub_section: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    fault_type: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    severity: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # The raw packed 4-byte code, stored for traceability/round-trip checks.
    # BigInteger (not Integer) because the 4-byte code is unsigned and
    # 0xFFFFFFFF (4294967295) overflows Postgres INTEGER (int32, max ~2.1e9).
    alarm_code: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
