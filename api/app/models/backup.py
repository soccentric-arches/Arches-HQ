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

    # Backup completion report from the device (Task.md C-12): the archive's
    # real name, size and checksum, replacing the estimate stored when the
    # SignedUploadUrl was issued.
    name: Mapped[str | None] = mapped_column(nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(nullable=True)
    upload_completed_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)
    success: Mapped[bool] = mapped_column(default=True)
