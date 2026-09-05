import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Guid, TimestampTZ
from app.models.enums import FaultSeverity
from app.models.mixins import UUIDPKMixin


class Fault(Base, UUIDPKMixin):
    """Raw, device-reported condition. HQ records what the device says,
    verbatim, with no interpretation layer -- see ARCHITECTURE.md §5.
    Alarms (a separate table) are the operator-facing interpretation.
    """

    __tablename__ = "fault"

    device_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("device.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(index=True)
    severity: Mapped[FaultSeverity] = mapped_column(Enum(FaultSeverity, name="fault_severity"))
    message: Mapped[str] = mapped_column(default="")
    raised_at: Mapped[datetime] = mapped_column(TimestampTZ, index=True)
    cleared_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)
