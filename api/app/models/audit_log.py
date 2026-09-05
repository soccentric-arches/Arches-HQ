import uuid

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Guid
from app.models.mixins import TenantScopedMixin


class AuditLog(Base, TenantScopedMixin):
    __tablename__ = "audit_log"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Guid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(index=True)
    target_device_id: Mapped[uuid.UUID | None] = mapped_column(
        Guid(), ForeignKey("device.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
