"""Static device groups: manual membership, used for deployment targeting
and (later) scoped access / per-group thresholds."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class DeviceGroup(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "device_group"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_device_group_tenant_name"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))

    members: Mapped[list["DeviceGroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class DeviceGroupMember(Base):
    __tablename__ = "device_group_member"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("device_group.id", ondelete="CASCADE"),
        primary_key=True,
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("device.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    group: Mapped[DeviceGroup] = relationship(back_populates="members")