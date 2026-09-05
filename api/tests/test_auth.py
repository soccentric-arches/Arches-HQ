"""Tests for plain email+password login (POST /auth/login)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from tests.factories import make_tenant, make_user

PASSWORD = "devpassword"


async def test_login_success_sets_session_cookie(client, db_session: AsyncSession):
    tenant = await make_tenant(db_session)
    user = await make_user(db_session, tenant, UserRole.admin, email="admin@example.com")
    await db_session.commit()

    res = await client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": PASSWORD},
    )
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert "archeshq_session" in res.cookies

    # The session cookie must actually work on /auth/me.
    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == user.email
    assert "password_hash" not in me.json()


async def test_login_wrong_password_rejected(client, db_session: AsyncSession):
    tenant = await make_tenant(db_session)
    await make_user(db_session, tenant, UserRole.admin, email="admin@example.com")
    await db_session.commit()

    res = await client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "not-the-password"},
    )
    assert res.status_code == 401


async def test_login_unknown_email_same_error_as_wrong_password(
    client, db_session: AsyncSession
):
    """Unknown email and wrong password must be indistinguishable (no user
    enumeration) -- same status, same message."""
    tenant = await make_tenant(db_session)
    await make_user(db_session, tenant, UserRole.admin, email="admin@example.com")
    await db_session.commit()

    wrong_pw = await client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "not-the-password"},
    )
    unknown = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "not-the-password"},
    )
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


async def test_login_user_without_password_rejected(client, db_session: AsyncSession):
    """A user row with no password set (e.g. pre-invited without one) cannot
    log in with an empty/garbage password."""
    tenant = await make_tenant(db_session)
    user = await make_user(db_session, tenant, UserRole.viewer)
    user.password_hash = None
    await db_session.commit()

    res = await client.post(
        "/auth/login", json={"email": user.email, "password": "whatever"}
    )
    assert res.status_code == 401


async def test_logout_clears_session(client, db_session: AsyncSession):
    tenant = await make_tenant(db_session)
    await make_user(db_session, tenant, UserRole.admin, email="admin@example.com")
    await db_session.commit()

    await client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": PASSWORD},
    )
    assert (await client.get("/auth/me")).status_code == 200

    res = await client.post("/auth/logout")
    assert res.status_code == 200
    # httpx's cookie jar drops the cookie on Set-Cookie with max_age=0 /
    # expiry in the past, so /auth/me now 401s.
    assert (await client.get("/auth/me")).status_code == 401


async def test_invite_requires_password_and_creates_working_login(
    client, db_session: AsyncSession
):
    """Admin invite now sets the initial password; the invited user can log
    in with it immediately."""
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    await db_session.commit()

    from tests.factories import login_as

    login_as(client, admin)

    # Missing/short password rejected.
    res = await client.post(
        "/users/invite", json={"email": "new@example.com", "role": "viewer"}
    )
    assert res.status_code == 422

    res = await client.post(
        "/users/invite",
        json={"email": "new@example.com", "role": "viewer", "password": "initial-pass-1"},
    )
    assert res.status_code == 201
    assert "password_hash" not in res.json()

    # The invited user logs in with the password the admin chose.
    login_res = await client.post(
        "/auth/login", json={"email": "new@example.com", "password": "initial-pass-1"}
    )
    assert login_res.status_code == 200