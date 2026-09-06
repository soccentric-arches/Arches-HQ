import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Guid, TimestampTZ
from app.models.enums import AlarmState, FaultSeverity
from app.models.mixins import UUIDPKMixin


class DeviceAlarm(Base, UUIDPKMixin):
    """A device-reported alarm stored in the literal ``alarms`` table (R3
    ingest path).

    This is distinct from the rule-based ``alarm`` table
    (``app.models.alarm.Alarm``), which records alarms raised by
    operator-configured ``AlarmRule`` rows. Device-reported alarms carry the
    packed 4-byte alarm code emitted by the device's alarms daemon plus its
    decoded fields, and have no originating rule.

    Layout of ``alarm_code`` (32-bit, *locked* -- the source of truth is
    ``Arches-Instrumentation/catalog/alarms.yaml`` and ``REQ.md`` section 8,
    from which the device's alarms daemon generates its C++ header):

      [31:28] domain (4 bits), [27:20] module (8 bits),
      [19:16] type (4 bits),   [15:0]  index (16 bits)

    Example from REQ.md section 8: the catalog spelling ``0x1_04_1_0007`` packs
    to ``0x10410007`` and reads as hardware / Hardware daemon / equipment /
    alarm 7, i.e. ``(domain=1, module=4, alarm_type=1, index=7)``.

    ``severity`` is NOT part of the code -- it is reported as its own field,
    because an alarm's severity can change over its life (X.733 severity-change
    events).

    This docstring previously asserted a four-equal-bytes layout ending in
    severity, and said it "MUST match the daemon's alarms_encode packing". It
    did not match: the byte boundaries fall inside the domain and module
    fields. A comment that confidently states a wrong contract is worse than no
    comment, because it gets trusted. See Task.md C-03/C-04.
    """

    __tablename__ = "alarms"

    device_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("device.id", ondelete="CASCADE"), index=True
    )
    # Decoded fields of the locked 32-bit layout (see the class docstring).
    domain: Mapped[int] = mapped_column(SmallInteger)          # 0..15
    module: Mapped[int] = mapped_column(SmallInteger)          # 0..255
    alarm_type: Mapped[int] = mapped_column(SmallInteger)      # 0..15
    # 0..65535, so SmallInteger (signed 16-bit) is too narrow -- Integer.
    alarm_index: Mapped[int] = mapped_column(Integer)
    # Reported alongside the code, not extracted from it. Stored as the X.733
    # level rather than an opaque byte.
    severity: Mapped[FaultSeverity] = mapped_column(
        Enum(FaultSeverity, name="fault_severity"), default=FaultSeverity.warning, index=True
    )
    # The raw packed 4-byte code, stored for traceability/round-trip checks.
    # BigInteger (not Integer): the 4-byte code is unsigned and 0xFFFFFFFF
    # (4294967295) overflows a 32-bit signed integer (max ~2.1e9).
    alarm_code: Mapped[int] = mapped_column(BigInteger)
    # Reuse the existing AlarmState enum so `clear` can set it to `resolved`.
    state: Mapped[AlarmState] = mapped_column(
        Enum(AlarmState, name="alarm_state"), default=AlarmState.active, index=True
    )
    triggered_at: Mapped[datetime] = mapped_column(TimestampTZ)
    resolved_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)
