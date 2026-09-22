"""Device-side auth: pairing-token redemption and per-session signature
verification (Task.md C-02).

Two authentication paths coexist:

* **Signature path (the recorded model).** At pairing the device presents a
  single-use pairing token plus the PUBLIC half of an Ed25519 key pair it
  generated itself. HQ stores the public key on the device row and issues no
  bearer credential at all. Every Heartbeat carries a signature over
  ``<device_id>|<sent_at_unix_ms>|<agent_version>`` which HQ verifies against
  that stored key, with a freshness window on ``sent_at`` so a captured
  frame cannot be replayed past it. Opening one device yields a private key
  that signs only for that device -- the property Instrumentation's REQ §9
  demands and a fleet-wide bearer token cannot provide.
* **Legacy token path.** Devices paired before the signature model keep
  exchanging a long-lived credential token (hashed at rest, same discipline
  as the REST API's app.services.credentials). They re-authenticate with it
  until they re-pair; new pairings never issue one.

Deliberately generic failure messages throughout: distinguishing expired
from used from unknown would turn the pairing endpoint into a token-guessing
oracle.
"""

import base64
import time
from datetime import UTC, datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.device_credential import DeviceCredential
from app.models.enums import CredentialKind, PairingState
from app.services.credentials import generate_token, hash_token

# Freshness window for a signed Heartbeat: generous enough for ordinary
# fleet clock skew (devices have no NTP guarantee at first boot), tight
# enough that a captured frame cannot be replayed beyond it. Two minutes.
SIGNATURE_FRESHNESS_S = 120


class PairingError(Exception):
    """Deliberately generic message for every failure mode (expired, used,
    unknown, wrong state) -- distinguishing them in the response would turn
    the pairing endpoint into a token-guessing oracle."""


def decode_device_pubkey(pubkey_b64: str) -> bytes:
    """Decode and shape-check a device session public key (32 raw bytes)."""
    try:
        raw = base64.b64decode(pubkey_b64, validate=True)
    except Exception as exc:  # noqa: BLE001 -- b64 errors are shape errors here
        raise PairingError("invalid pairing request") from exc
    if len(raw) != 32:
        raise PairingError("invalid pairing request")
    return raw


async def redeem_pairing_token(
    session: AsyncSession, raw_token: str, pubkey_b64: str = ""
) -> tuple[Device, str]:
    """Consume a single-use pairing token and pair the device.

    With ``pubkey_b64`` set (the C-02 signature model) the key is bound to
    the device and NO long-lived credential is issued -- the device
    authenticates by signing from then on. Without it the legacy flow
    issues a long-lived bearer credential exactly as before. Returns
    ``(device, credential_token_or_empty)``.
    """
    if pubkey_b64:
        decode_device_pubkey(pubkey_b64)  # shape-check before anything else

    token_hash = hash_token(raw_token)
    cred = (
        await session.execute(
            select(DeviceCredential).where(DeviceCredential.token_hash == token_hash)
        )
    ).scalar_one_or_none()

    now = datetime.now(UTC)
    if (
        cred is None
        or cred.kind != CredentialKind.pairing
        or cred.revoked_at is not None
        or cred.expires_at is None
        or cred.expires_at < now
    ):
        raise PairingError("invalid or expired pairing token")

    device = await session.get(Device, cred.device_id)
    if device is None or device.pairing_state != PairingState.pending:
        raise PairingError("device not in a pairable state")

    cred.revoked_at = now  # single-use: consume it immediately

    if pubkey_b64:
        # Signature model: bind the device-generated public key; HQ keeps
        # only the public half, and no bearer credential is issued.
        device.agent_pubkey = pubkey_b64
        device.pairing_state = PairingState.authorized
        await session.flush()
        return device, ""

    # Legacy pairing: issue a bearer credential exactly as before C-02.
    raw = issue_legacy_credential(session, device)
    device.pairing_state = PairingState.authorized
    await session.flush()
    return device, raw


def verify_heartbeat_signature(device: Device, heartbeat) -> bool:
    """Verify a signed Heartbeat against the key bound at pairing.

    The signed message is ``device_id|sent_at_unix_ms|agent_version`` with
    the pipe separators; the freshness window bounds replay. Returns True
    only when the device has a bound key, the signature verifies and
    ``sent_at`` is inside the window.
    """
    if not device.agent_pubkey or not heartbeat.sig_b64:
        return False
    try:
        raw = base64.b64decode(device.agent_pubkey, validate=True)
        if len(raw) != 32:
            return False
        key = Ed25519PublicKey.from_public_bytes(raw)
        message = (
            f"{heartbeat.device_id}|{heartbeat.sent_at_unix_ms}|{heartbeat.agent_version}"
        ).encode()
        key.verify(base64.b64decode(heartbeat.sig_b64, validate=True), message)
    except (InvalidSignature, ValueError):
        return False
    skew = abs(time.time() * 1000 - heartbeat.sent_at_unix_ms) / 1000.0
    return skew <= SIGNATURE_FRESHNESS_S


async def validate_heartbeat(session: AsyncSession, device_id: str, heartbeat) -> Device | None:
    """Returns the Device when the heartbeat authenticates it and the device
    isn't disabled/revoked, else None. Signature path first (C-02); the
    legacy token path applies only to devices without a bound signing key.
    """
    device = await session.get(Device, device_id)
    if device is not None and verify_heartbeat_signature(device, heartbeat):
        if device.pairing_state in (PairingState.disabled, PairingState.revoked):
            return None
        return device
    return await validate_long_lived_credential(session, device_id, heartbeat.credential_token)


async def validate_long_lived_credential(
    session: AsyncSession, device_id: str, raw_token: str
) -> Device | None:
    """Returns the Device if the credential is live and the device isn't
    disabled/revoked, else None. Checked on every frame by the caller, not
    just at connect -- disable must cut off an already-connected device too
    (ARCHITECTURE.md §5 / IMPLEMENTATION_PLAN §4.3)."""
    if not raw_token:
        return None
    token_hash = hash_token(raw_token)
    cred = (
        await session.execute(
            select(DeviceCredential).where(
                DeviceCredential.device_id == device_id,
                DeviceCredential.token_hash == token_hash,
                DeviceCredential.kind == CredentialKind.long_lived,
                DeviceCredential.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if cred is None:
        return None

    device = await session.get(Device, device_id)
    if device is None or device.pairing_state in (PairingState.disabled, PairingState.revoked):
        return None
    return device


def issue_legacy_credential(session: AsyncSession, device: Device) -> str:
    """Issue a long-lived bearer credential for a legacy pairing (a device
    that paired without presenting a signing key). New pairings (C-02) never
    call this. Returns the raw token; only its hash is stored.
    """
    raw = generate_token()
    session.add(
        DeviceCredential(
            device_id=device.id,
            kind=CredentialKind.long_lived,
            token_hash=hash_token(raw),
        )
    )
    return raw