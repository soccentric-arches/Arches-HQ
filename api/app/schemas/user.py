from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class UserInvite(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.viewer
    # Initial login password, chosen by the inviting admin.
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: UserRole
    created_at: datetime
    # password_hash deliberately excluded -- never leak credential material.
