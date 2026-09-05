from sqlalchemy import event
import uuid
from datetime import UTC, datetime

from sqlalchemy import String, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Guid(TypeDecorator):
    """Platform-independent UUID column.

    Accepts `uuid.UUID` or canonical string on bind (the gateway receives
    device ids as strings off the wire), stores as native Uuid on Postgres
    and CHAR(32) on SQLite.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            value = uuid.UUID(value)
        return value.hex

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


class TimestampTZ(TypeDecorator):
    """Timezone-aware UTC timestamp. SQLite stores naive text, so values
    are normalized to UTC ISO-8601 on bind and re-hydrated with tzinfo on
    result (Postgres keeps its native timestamptz behavior)."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str | None = None):
    settings = get_settings()
    engine = create_async_engine(database_url or settings.database_url, pool_pre_ping=True)
    # SQLite does not enforce foreign keys (and therefore ON DELETE CASCADE)
    # unless the pragma is set per connection.
    if engine.url.get_backend_name() == "sqlite":

        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_fk(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = make_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


def configure_for_tests(database_url: str) -> None:
    """Point the module-level engine/session factory at a test database.

    Must be called before any request touches get_db(); tests do this in a
    fixture before the app is exercised.
    """
    global _engine, _session_factory
    _engine = make_engine(database_url)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
