import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Guid, TimestampTZ
from app.models.mixins import UUIDPKMixin


class LogBundle(Base, UUIDPKMixin):
    __tablename__ = "log_bundle"

    device_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("device.id", ondelete="CASCADE"), index=True
    )
    storage_url: Mapped[str]
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(TimestampTZ)
    time_range_start: Mapped[datetime] = mapped_column(TimestampTZ)
    time_range_end: Mapped[datetime] = mapped_column(TimestampTZ)
