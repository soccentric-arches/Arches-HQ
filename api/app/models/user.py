from sqlalchemy import Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import UserRole
from app.models.mixins import TenantScopedMixin


class User(Base, TenantScopedMixin):
    __tablename__ = "user"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),)

    email: Mapped[str] = mapped_column(index=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.viewer
    )
    # bcrypt hash of the login password. Nullable so a pre-invited user row
    # can exist (with a password set at invite time) before first login.
    password_hash: Mapped[str | None] = mapped_column(nullable=True)
