from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import SESSION_COOKIE_NAME, get_current_context
from app.auth.pwd import verify_password
from app.auth.session import issue_session_token
from app.config import get_settings
from app.db.deps import get_db
from app.models.user import User
from app.schemas.user import UserOut
from app.services import audit
from app.services.tenant_repo import TenantContext

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = (
        await db.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()

    # Same error + timing whether the user exists or the password is wrong,
    # so the endpoint doesn't leak which emails are invited.
    if user is None or user.password_hash is None or not verify_password(
        body.password, user.password_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")

    session_token = issue_session_token(user.id, user.tenant_id, user.role.value)
    ctx = TenantContext(tenant_id=user.tenant_id, user_id=user.id, role=user.role.value)
    await audit.record(db, ctx, "auth.login")
    await db.commit()

    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        httponly=True,
        samesite="lax",
        secure=settings.env != "dev",
        max_age=settings.session_ttl_seconds,
    )
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response, ctx: TenantContext = Depends(get_current_context)):
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(get_current_context),
):
    user = (await db.execute(select(User).where(User.id == ctx.user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session user no longer exists")
    return UserOut.model_validate(user)