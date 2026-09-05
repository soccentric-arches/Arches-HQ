"""Freeform device tags: simple labels for filtering and grouping-lite."""

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Guid
from app.models.mixins import UUIDPKMixin


class DeviceTag(Base, UUIDPKMixin):
    __tablename__ = "device_tag"
    __table_args__ = (UniqueConstraint("device_id", "tag", name="uq_device_tag"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("tenant.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("device.id", ondelete="CASCADE"), index=True
    )
    tag: Mapped[str] = mapped_column(String(64))