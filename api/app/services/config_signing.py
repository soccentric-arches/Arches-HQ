"""HQ's Ed25519 configuration-signing key (Task.md C-10).

The signed-config push replaced the bare ApplyConfig notification: the
gateway now sends ``ServerFrame(signed_config=...)`` whose signature the
device verifies BEFORE applying, so tunnel compromise alone cannot
reconfigure a device. The device holds only this key's PUBLIC half
(delivered in PairingResult at pairing, over the pairing-token
authenticated exchange) -- the private half never leaves HQ, which is the
property C-02 demands ("opening one device does not yield the ability to
sign for the fleet").

Signature format matches the device's verify path exactly
(Arches-Instrumentation ConfigService.apply_signed): Ed25519 over
``<daemon>|<yaml>``, 64 raw bytes.

Key management: the private key is loaded from the
``ARCHESHQ_CONFIG_SIGNING_KEY`` env var (base64 raw 32-byte seed) when set
-- that is the production form -- or, for development and tests, generated
once and persisted under the storage directory so restarts keep signing
with the same key and devices that learned the public half at pairing stay
valid. Rotating the key means publishing a new key id: devices trust
several ids at once (see Instrumentation ConfigService.add_signing_key), so
there is no flag day.
"""

import base64
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config import get_settings

# The key id devices see on SignedConfig frames and trust from pairing on.
# Bump when the signing key rotates; old ids stay trusted on the device
# until retired, so push with the new id and retire later.
CONFIG_SIGNING_KEY_ID = "hq-config-2026-09"


class ConfigSigningKey:
    """The fleet's Ed25519 config-signing key pair."""

    def __init__(self, private_key: Ed25519PrivateKey, key_id: str = CONFIG_SIGNING_KEY_ID):
        self.private_key = private_key
        self.key_id = key_id

    @property
    def public_key_raw32(self) -> bytes:
        return self.private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )

    @property
    def public_key_b64(self) -> str:
        return base64.b64encode(self.public_key_raw32).decode()

    def sign(self, message: bytes) -> bytes:
        return self.private_key.sign(message)

    def sign_config(self, daemon: str, yaml_text: str) -> bytes:
        """Sign exactly the bytes the device verifies: ``daemon|yaml``."""
        return self.sign(f"{daemon}|{yaml_text}".encode())


def _dev_key_path() -> Path:
    return Path(get_settings().storage_dir) / "config_signing_key.seed"


@lru_cache
def get_config_signing_key() -> ConfigSigningKey:
    """Load or (dev-only) create the fleet config-signing key.

    Production supplies the seed via ``ARCHESHQ_CONFIG_SIGNING_KEY`` so the
    key never rests in a writable directory; without it the key is generated
    and persisted under the storage directory, which is fine for development
    and the test suites and clearly not a production secret store.
    """
    seed_b64 = get_settings().config_signing_key
    if seed_b64:
        seed = base64.b64decode(seed_b64)
        if len(seed) != 32:
            raise ValueError(
                "ARCHESHQ_CONFIG_SIGNING_KEY must be 32 raw bytes, base64-encoded"
            )
        private_key = Ed25519PrivateKey.from_private_bytes(seed)
    else:
        path = _dev_key_path()
        if path.is_file():
            seed = base64.b64decode(path.read_text().strip())
            private_key = Ed25519PrivateKey.from_private_bytes(seed)
        else:
            private_key = Ed25519PrivateKey.generate()
            path.parent.mkdir(parents=True, exist_ok=True)
            seed = private_key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
            path.write_text(base64.b64encode(seed).decode())
    return ConfigSigningKey(private_key)