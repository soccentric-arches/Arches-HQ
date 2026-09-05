"""Desired device configuration, held per section.

HQ is the source of truth for *intent*: an operator edits a section (time
sync, network, security, system identity) here and the device agent applies
it device-side (Arches-Configuration owns the application; HQ notifies via
an ApplyConfig command). One row per (device, section).
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Guid, TimestampTZ

CONFIG_SECTIONS = ("system", "time", "network", "security")


class DeviceConfig(Base):
    __tablename__ = "device_config"
    __table_args__ = (UniqueConstraint("device_id", "section", name="uq_device_config_section"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        Guid(), ForeignKey("device.id", ondelete="CASCADE"), primary_key=True
    )
    section: Mapped[str] = mapped_column(String(32), primary_key=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(TimestampTZ)