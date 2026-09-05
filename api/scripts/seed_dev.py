"""Seed a dev tenant + admin user + the nine platform devices so there's
something to log in as and manage. Not for production use -- there is no
tenant self-signup flow yet (ARCHITECTURE.md §6, single shared deployment
assumption).

Usage:
  python -m scripts.seed_dev --email you@example.com --password secret123
  python -m scripts.seed_dev --devices-only          # devices only, no user changes

Devices: one per platform family in the project-managers fleet, named
<platform>-0001 (acadia-0001 … zion-0001). Any other device in the tenant
(e.g. a manually created "Demo" device) is removed.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.auth.pwd import hash_password
from app.db.base import get_session_factory
from app.models.device import Device
from app.models.enums import UserRole
from app.models.tenant import Tenant
from app.models.user import User

# The nine platform families in the project-managers fleet, one device each.
PLATFORM_NAMES = (
    "acadia",
    "arches",
    "joshua",
    "orion",
    "pinnacle",
    "polaris",
    "sequoia",
    "vela",
    "zion",
)
PLATFORM_DEVICES = [f"{name}-0001" for name in PLATFORM_NAMES]


async def get_or_create_tenant(session, tenant_name: str) -> Tenant:
    tenant_result = await session.execute(select(Tenant).where(Tenant.name == tenant_name))
    tenant = tenant_result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(name=tenant_name)
        session.add(tenant)
        await session.flush()
        print(f"created tenant {tenant.name} ({tenant.id})")
    return tenant


async def seed_devices(session, tenant: Tenant) -> None:
    """Ensure the nine <platform>-0001 devices exist; remove anything else
    (e.g. the old manually created "Demo" device). Idempotent."""
    devices = (
        (await session.execute(select(Device).where(Device.tenant_id == tenant.id)))
        .scalars()
        .all()
    )
    existing_names = {d.name for d in devices}

    for name in PLATFORM_DEVICES:
        if name not in existing_names:
            session.add(Device(tenant_id=tenant.id, name=name))
            print(f"created device {name}")

    for device in devices:
        if device.name not in PLATFORM_DEVICES:
            await session.delete(device)
            print(f"removed device {device.name}")


async def seed(email: str, password: str, tenant_name: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = await get_or_create_tenant(session, tenant_name)

        user_result = await session.execute(
            select(User).where(User.tenant_id == tenant.id, User.email == email)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            user = User(
                tenant_id=tenant.id,
                email=email,
                role=UserRole.admin,
                password_hash=hash_password(password),
            )
            session.add(user)
            print(f"created admin user {email}")
        else:
            user.role = UserRole.admin
            user.password_hash = hash_password(password)
            print(f"{email} already exists, ensured admin role + new password")

        await seed_devices(session, tenant)
        await session.commit()


async def seed_devices_only(tenant_name: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant_result = await session.execute(select(Tenant).where(Tenant.name == tenant_name))
        tenant = tenant_result.scalar_one_or_none()
        if tenant is None:
            raise SystemExit(f"tenant {tenant_name!r} not found -- run the full seed first")
        await seed_devices(session, tenant)
        await session.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--tenant", default="Dev Tenant")
    parser.add_argument(
        "--devices-only",
        action="store_true",
        help="only ensure the platform devices / remove others; leave users untouched",
    )
    args = parser.parse_args()

    if args.devices_only:
        asyncio.run(seed_devices_only(args.tenant))
    else:
        if not args.email or not args.password:
            parser.error("--email and --password are required unless --devices-only is given")
        asyncio.run(seed(args.email, args.password, args.tenant))