import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Guid, TimestampTZ
from app.models.mixins import UUIDPKMixin


class Backup(Base, UUIDPKMixin):
    __tablename__ = "backup"

    device_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("device.id", ondelete="CASCADE"), index=True
    )
    storage_url: Mapped[str]
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ)
    restored_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)
