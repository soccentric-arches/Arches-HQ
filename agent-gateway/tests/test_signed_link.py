"""Tests for the retargeted device↔HQ link: signature pairing (C-02),
AlarmEvent ingest (C-06), BackupStatus (C-12), SignedConfig push (C-10),
AgentReport health promotion (F-05) and telemetry metadata (C-08).
"""

import base64
import json
import time
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from sqlalchemy import select

from app.models.backup import Backup
from app.models.device_alarm import DeviceAlarm
from app.models.enums import AlarmState, CommandKind, FaultSeverity, PairingState
from app.models.pending_command import PendingCommand
from app.models.telemetry import TelemetrySample
from app.services import config_signing
from archeshq.agent_pb2 import (
    AgentFrame,
    AlarmEvent,
    BackupStatus,
    Heartbeat,
    PairingHandshake,
    TelemetryBatch,
    TelemetrySample as PbSample,
)
from gateway import handlers
from tests.factories import (
    make_authorized_device_with_credential,
    make_pending_device_with_pairing_token,
    make_tenant,
)


class DeviceKeys:
    """Stand-in for the device's Ed25519 key pair (C-02: generated on the
    device; only the public half ever reaches HQ)."""

    def __init__(self):
        self.private = Ed25519PrivateKey.generate()

    @property
    def pubkey_b64(self) -> str:
        raw = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return base64.b64encode(raw).decode()

    def sign(self, message: bytes) -> str:
        return base64.b64encode(self.private.sign(message)).decode()


def _now_ms() -> int:
    return int(time.time() * 1000)


# ---- C-02: signature pairing and heartbeat auth -----------------------------


async def test_signature_pairing_issues_no_bearer_and_returns_config_pubkey(
    gateway_stub, db_session
):
    tenant = await make_tenant(db_session)
    device, token = await make_pending_device_with_pairing_token(db_session, tenant)
    keys = DeviceKeys()

    async def pair_frames():
        yield AgentFrame(
            pairing_handshake=PairingHandshake(pairing_token=token, pubkey_b64=keys.pubkey_b64)
        )

    response = None
    async for frame in gateway_stub.Connect(pair_frames()):
        response = frame
        break

    assert response.pairing_result.success is True
    # No bearer credential is issued under the signature model.
    assert response.pairing_result.credential_token == ""
    # HQ's config-signing public key comes back over the pairing exchange
    # (C-10): the device learns it here, from a token-authenticated channel.
    assert response.pairing_result.config_pubkey_b64
    assert response.pairing_result.config_key_id
    assert len(base64.b64decode(response.pairing_result.config_pubkey_b64)) == 32

    await db_session.refresh(device)
    assert device.agent_pubkey == keys.pubkey_b64
    assert device.pairing_state == PairingState.authorized


async def test_legacy_pairing_without_pubkey_still_issues_credential(gateway_stub, db_session):
    tenant = await make_tenant(db_session)
    device, token = await make_pending_device_with_pairing_token(db_session, tenant)

    async def pair_frames():
        yield AgentFrame(pairing_handshake=PairingHandshake(pairing_token=token))

    response = None
    async for frame in gateway_stub.Connect(pair_frames()):
        response = frame
        break

    assert response.pairing_result.success is True
    assert response.pairing_result.credential_token
    await db_session.refresh(device)
    assert device.agent_pubkey is None


async def test_signed_heartbeat_authenticates(db_session):
    from gateway.auth import validate_heartbeat

    tenant = await make_tenant(db_session)
    device, _ = await make_pending_device_with_pairing_token(db_session, tenant)
    keys = DeviceKeys()
    device.agent_pubkey = keys.pubkey_b64
    await db_session.commit()

    now_ms = _now_ms()
    hb = Heartbeat(
        device_id=str(device.id),
        sent_at_unix_ms=now_ms,
        agent_version="2.0.0",
        sig_b64=keys.sign(f"{device.id}|{now_ms}|2.0.0".encode()),
    )
    authenticated = await validate_heartbeat(db_session, str(device.id), hb)
    assert authenticated is not None
    assert authenticated.id == device.id


async def test_tampered_heartbeat_signature_is_rejected(db_session):
    from gateway.auth import validate_heartbeat

    tenant = await make_tenant(db_session)
    device, _ = await make_pending_device_with_pairing_token(db_session, tenant)
    keys = DeviceKeys()
    device.agent_pubkey = keys.pubkey_b64
    await db_session.commit()

    now_ms = _now_ms()
    attacker = Ed25519PrivateKey.generate()  # wrong key
    hb = Heartbeat(
        device_id=str(device.id),
        sent_at_unix_ms=now_ms,
        agent_version="2.0.0",
        sig_b64=base64.b64encode(
            attacker.sign(f"{device.id}|{now_ms}|2.0.0".encode())
        ).decode(),
    )
    assert await validate_heartbeat(db_session, str(device.id), hb) is None


async def test_stale_heartbeat_signature_is_rejected(db_session):
    from gateway.auth import SIGNATURE_FRESHNESS_S, validate_heartbeat

    tenant = await make_tenant(db_session)
    device, _ = await make_pending_device_with_pairing_token(db_session, tenant)
    keys = DeviceKeys()
    device.agent_pubkey = keys.pubkey_b64
    await db_session.commit()

    stale_ms = int((time.time() - SIGNATURE_FRESHNESS_S - 30) * 1000)
    hb = Heartbeat(
        device_id=str(device.id),
        sent_at_unix_ms=stale_ms,
        agent_version="2.0.0",
        sig_b64=keys.sign(f"{device.id}|{stale_ms}|2.0.0".encode()),
    )
    assert await validate_heartbeat(db_session, str(device.id), hb) is None


async def test_invalid_pubkey_shape_is_rejected_at_pairing(gateway_stub, db_session):
    tenant = await make_tenant(db_session)
    _, token = await make_pending_device_with_pairing_token(db_session, tenant)

    async def pair_frames():
        yield AgentFrame(
            pairing_handshake=PairingHandshake(pairing_token=token, pubkey_b64="not-base64!!")
        )

    response = None
    async for frame in gateway_stub.Connect(pair_frames()):
        response = frame
        break

    assert response.pairing_result.success is False


# ---- C-10: signed config push ------------------------------------------------


async def test_apply_config_command_becomes_signed_config_frame(db_session):
    from app.models.device_config import DeviceConfig

    tenant = await make_tenant(db_session)
    device, _ = await make_authorized_device_with_credential(db_session, tenant)

    db_session.add(
        DeviceConfig(
            device_id=device.id,
            section="network",
            config={"firewall": {"ssh": False}},
            updated_at=datetime.now(UTC),
        )
    )
    command_id = f"config:{device.id}:network:1"
    db_session.add(
        PendingCommand(
            device_id=device.id,
            command_id=command_id,
            kind=CommandKind.apply_config,
            payload={"section": "network"},
        )
    )
    await db_session.commit()

    frames = await handlers.drain_pending_commands(db_session, device.id)
    signed = [f for f in frames if f.HasField("signed_config")]
    assert len(signed) == 1
    frame = signed[0]
    # Section maps onto the device daemon that owns it (C-10 mapping table).
    assert frame.signed_config.daemon == "networkd"
    assert "ssh" in frame.signed_config.yaml
    assert frame.signed_config.key_id == config_signing.CONFIG_SIGNING_KEY_ID

    # The signature verifies against the fleet key exactly the way the
    # device's verify-before-apply path checks it (Instrumentation §9).
    key = config_signing.get_config_signing_key()
    Ed25519PublicKey.from_public_bytes(key.public_key_raw32).verify(
        frame.signed_config.signature,
        f"{frame.signed_config.daemon}|{frame.signed_config.yaml}".encode(),
    )


# ---- C-06: alarm transport ---------------------------------------------------


async def test_alarm_event_raise_creates_row(db_session):
    tenant = await make_tenant(db_session)
    device, _ = await make_authorized_device_with_credential(db_session, tenant)

    code = 0x10410007
    now_ms = _now_ms()
    await handle(
        handlers.handle_alarm_event,
        db_session,
        device,
        AlarmEvent(
            alarm_id=code,
            action=AlarmEvent.RAISE,
            severity=__severity("MAJOR"),
            owner="arches-client",
            additional_text="run aborted",
            count=3,
            acknowledged=False,
            needs_snapshot=True,
            first_seen_unix_ms=now_ms - 5000,
            last_seen_unix_ms=now_ms,
            correlated=[0x10410008],
        ),
    )
    await db_session.commit()

    row = (await db_session.execute(select(DeviceAlarm))).scalars().one()
    assert row.alarm_code == code
    assert (row.domain, row.module, row.alarm_type, row.alarm_index) == (1, 4, 1, 7)
    assert row.severity == FaultSeverity.major
    assert row.owner == "arches-client"
    assert row.count == 3
    assert row.needs_snapshot is True
    assert row.correlated == [0x10410008]
    assert row.state == AlarmState.active


async def test_alarm_event_clear_resolves(db_session):
    tenant = await make_tenant(db_session)
    device, _ = await make_authorized_device_with_credential(db_session, tenant)

    code = 0x10410007
    now_ms = _now_ms()
    await handle(
        handlers.handle_alarm_event,
        db_session,
        device,
        AlarmEvent(
            alarm_id=code,
            action=AlarmEvent.RAISE,
            first_seen_unix_ms=now_ms,
            last_seen_unix_ms=now_ms,
        ),
    )
    await handle(
        handlers.handle_alarm_event,
        db_session,
        device,
        AlarmEvent(alarm_id=code, action=AlarmEvent.CLEAR, last_seen_unix_ms=now_ms + 5),
    )
    await db_session.commit()

    row = (await db_session.execute(select(DeviceAlarm))).scalars().one()
    assert row.state == AlarmState.resolved
    assert row.resolved_at is not None


async def test_alarm_severity_change_updates_existing_row(db_session):
    tenant = await make_tenant(db_session)
    device, _ = await make_authorized_device_with_credential(db_session, tenant)

    code = 0x10410007
    now_ms = _now_ms()
    await handle(
        handlers.handle_alarm_event,
        db_session,
        device,
        AlarmEvent(
            alarm_id=code,
            action=AlarmEvent.RAISE,
            first_seen_unix_ms=now_ms,
            last_seen_unix_ms=now_ms,
        ),
    )
    await handle(
        handlers.handle_alarm_event,
        db_session,
        device,
        AlarmEvent(
            alarm_id=code,
            action=AlarmEvent.SEVERITY_CHANGE,
            severity=__severity("CRITICAL"),
            count=5,
            last_seen_unix_ms=now_ms + 10,
        ),
    )
    await db_session.commit()

    rows = (await db_session.execute(select(DeviceAlarm))).scalars().all()
    assert len(rows) == 1  # upsert, not stack
    assert rows[0].severity == FaultSeverity.critical
    assert rows[0].count == 5


def __severity(name: str):
    from archeshq.agent_pb2 import FaultEvent

    return FaultEvent.Severity.Value(name)


async def handle(fn, *args):
    return await fn(*args)


# ---- C-12: backup completion -------------------------------------------------


async def test_backup_status_completes_row(db_session):

    tenant = await make_tenant(db_session)
    device, _ = await make_authorized_device_with_credential(db_session, tenant)

    now_ms = _now_ms()
    await handlers.handle_backup_status(
        db_session,
        device,
        BackupStatus(
            name="backup-2026.tar.gz",
            size_bytes=1048576,
            created_at_unix_ms=now_ms,
            checksum_sha256="deadbeef" * 8,
            success=True,
        ),
    )
    await db_session.commit()

    row = (await db_session.execute(select(Backup))).scalars().one()
    assert row.name == "backup-2026.tar.gz"
    assert row.size_bytes == 1048576
    assert row.checksum_sha256 == "deadbeef" * 8
    assert row.upload_completed_at is not None
    assert row.success is True


# ---- F-05: health/spoke promotion ---------------------------------------------


async def test_agent_report_promotes_health_and_spokes(db_session):
    tenant = await make_tenant(db_session)
    device, _ = await make_authorized_device_with_credential(db_session, tenant)

    report = {
        "health_score": 0.82,
        "spokes": [
            {"name": "networkd", "state": "ready", "live": True},
            {"name": "ota", "state": "degraded", "live": False},
        ],
        "hardware": {"serial": "JET-1"},
    }
    await handlers.handle_agent_report(db_session, device, json.dumps(report))
    await db_session.commit()
    await db_session.refresh(device)

    assert device.health_score == pytest.approx(0.82)
    assert device.spoke_status[1]["state"] == "degraded"
    assert device.reported["spokes"][0]["name"] == "networkd"


# ---- C-08: telemetry metadata --------------------------------------------------


async def test_telemetry_sample_carries_unit_and_type(db_session):
    tenant = await make_tenant(db_session)
    device, _ = await make_authorized_device_with_credential(db_session, tenant)

    now_ms = _now_ms()
    await handlers.handle_telemetry_batch(
        db_session,
        device,
        TelemetryBatch(
            samples=[
                PbSample(
                    metric="cpu_load",
                    value=0.5,
                    recorded_at_unix_ms=now_ms,
                    unit="percent",
                    metric_type="gauge",
                )
            ]
        ),
    )
    await db_session.commit()

    row = (await db_session.execute(select(TelemetrySample))).scalars().one()
    assert row.unit == "percent"
    assert row.metric_type == "gauge"


# ---- C-07: catalog consumed at render -------------------------------------------


async def test_catalog_decodes_worked_example():
    from app.services import alarms_catalog

    entry = alarms_catalog.lookup(0x10410007)
    assert entry is not None
    assert entry.name == "hw_device_fail"
    assert (entry.domain, entry.module, entry.alarm_type, entry.index) == (1, 4, 1, 7)
    assert entry.probable_cause
    assert entry.description
    # Round-trip: encode(decode(x)) == x for a sample of the catalog.
    code = entry.code
    assert alarms_catalog.encode_alarm_code(
        entry.domain, entry.module, entry.alarm_type, entry.index
    ) == code


async def test_catalog_hq_reportable_filter_respected():
    from app.services import alarms_catalog

    entries = alarms_catalog.load_catalog()
    withheld = [code for code, e in entries.items() if not e.hq_reportable]
    assert withheld, "catalog carries hq_reportable=false entries; the filter must see them"
    for code in withheld:
        assert alarms_catalog.reportable(code) is False