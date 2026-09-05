from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root (config.py lives at <root>/api/app/config.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARCHESHQ_", env_file=".env", extra="ignore")

    env: str = "dev"

    # SQLite everywhere: one HQ database + one file per device, all
    # under the storage root (ARCHESHQ_STORAGE_DIR in docker).
    database_url: str = f"sqlite+aiosqlite:///{_REPO_ROOT / 'storage' / 'hq.sqlite'}"

    # Session JWT issued by the API after username+password login, stored in
    # an httpOnly cookie.
    session_secret_key: str = "dev-only-change-me-in-every-real-deployment"
    session_algorithm: str = "HS256"
    session_ttl_seconds: int = 60 * 60 * 8

    # Object storage (S3-compatible; MinIO in local dev).
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "archeshq"
    s3_secret_key: str = "archeshq-dev-secret"
    s3_bucket: str = "archeshq"
    s3_region: str = "us-east-1"

    # Filesystem storage root for everything persistent that is not the
    # Postgres data dir: per-device folders (SQLite mirror, exports) and
    # OTA artifact staging. Docker bind-mounts it from ./storage.
    storage_dir: str = str(_REPO_ROOT / "storage")

    # Redis (arq background jobs).
    redis_url: str = "redis://localhost:6379/0"

    # Presence / heartbeat.
    heartbeat_interval_s: int = 30
    heartbeat_missed_threshold: int = 2  # offline after N missed intervals

    # Pairing tokens.
    pairing_token_ttl_seconds: int = 15 * 60

    cors_allow_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
