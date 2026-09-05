import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Guid, TimestampTZ
from app.models.enums import DeviceRolloutStatus, RolloutStatus, RolloutTarget
from app.models.mixins import TenantScopedMixin, UUIDPKMixin


class UpdateArtifact(Base, TenantScopedMixin):
    __tablename__ = "update_artifact"
    __table_args__ = (UniqueConstraint("tenant_id", "version", name="uq_artifact_tenant_version"),)

    version: Mapped[str]
    target_board_rev: Mapped[str]
    storage_url: Mapped[str]
    checksum_sha256: Mapped[str]


class UpdateRollout(Base, UUIDPKMixin):
    __tablename__ = "update_rollout"

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("update_artifact.id", ondelete="CASCADE"), index=True
    )
    target: Mapped[RolloutTarget] = mapped_column(Enum(RolloutTarget, name="rollout_target"))
    # Populated when target == specific_devices / device_group; e.g.
    # {"device_ids": [...]}, {"group": "canary"}. `all` leaves this empty.
    target_selector: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[RolloutStatus] = mapped_column(
        Enum(RolloutStatus, name="rollout_status"), default=RolloutStatus.pending
    )
    started_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)


class UpdateRolloutDevice(Base):
    __tablename__ = "update_rollout_device"

    rollout_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("update_rollout.id", ondelete="CASCADE"), primary_key=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("device.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[DeviceRolloutStatus] = mapped_column(
        Enum(DeviceRolloutStatus, name="device_rollout_status"), default=DeviceRolloutStatus.pending
    )
    applied_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)
    error: Mapped[str | None] = mapped_column(nullable=True)
