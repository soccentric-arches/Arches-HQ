import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Guid, TimestampTZ
from app.models.mixins import UUIDPKMixin


class TelemetrySample(Base, UUIDPKMixin):
    __tablename__ = "telemetry_sample"
    __table_args__ = (
        Index("ix_telemetry_device_metric_time", "device_id", "metric", "recorded_at"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("device.id", ondelete="CASCADE"), index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(TimestampTZ, index=True)
    metric: Mapped[str] = mapped_column(index=True)
    value: Mapped[float] = mapped_column(Float)
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
