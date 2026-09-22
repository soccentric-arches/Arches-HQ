"""Per-frame-type business logic, kept out of servicer.py so the gRPC glue
stays readable. Each handler takes the open DB session for this frame and
the device it belongs to.
"""

import json
import logging
import uuid
from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alarm import Alarm, AlarmRule
from app.models.backup import Backup
from app.models.device import Device
from app.models.device_alarm import DeviceAlarm
from app.models.enums import AlarmState, CommandKind, FaultSeverity
from app.models.fault import Fault
from app.models.log_bundle import LogBundle
from app.models.pending_command import PendingCommand
from app.models.telemetry import TelemetrySample
from app.models.update import DeviceRolloutStatus, RolloutStatus, UpdateRollout, UpdateRolloutDevice
from app.services import alarms_catalog, config_signing
from app.services.storage import new_object_id, object_key, presigned_upload_url
from archeshq.agent_pb2 import (
    AlarmEvent,
    ApplyConfig,
    ApplyUpdate,
    BackupStatus,
    Command,
    FactoryReset,
    FaultEvent,
    Location,
    LogUploadRequest,
    Reboot,
    Restore,
    ServerFrame,
    Shutdown,
    SignedConfig,
    TakeBackupNow,
    TelemetryBatch,
)

logger = logging.getLogger("gateway.handlers")

# Wire severity -> stored severity. WARN is X.733's "warning"; the proto keeps
# the shorter spelling for compatibility with deployed agents (Task.md C-05).
_SEVERITY_MAP = {
    FaultEvent.INFO: FaultSeverity.info,
    FaultEvent.WARN: FaultSeverity.warning,
    FaultEvent.CRITICAL: FaultSeverity.critical,
    FaultEvent.MINOR: FaultSeverity.minor,
    FaultEvent.MAJOR: FaultSeverity.major,
}

# X.733 wire severity spelled by AlarmEvent (C-06) shares FaultEvent.Severity.
_ALARM_SEVERITY_MAP = _SEVERITY_MAP

# HQ's four config sections map onto the device daemons that own them
# (Task.md C-10). istate is the hub: system and time policy are its own
# config; network and security (firewall, ssh, tunnel) live in networkd. The
# mapping is explicit here so the section names stay UI vocabulary, not wire
# vocabulary.
_SECTION_TO_DAEMON = {
    "system": "istate",
    "time": "istate",
    "network": "networkd",
    "security": "networkd",
}


def _ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


async def handle_telemetry_batch(
    session: AsyncSession, device: Device, batch: TelemetryBatch
) -> None:
    for sample in batch.samples:
        session.add(
            TelemetrySample(
                device_id=device.id,
                recorded_at=_ms_to_dt(sample.recorded_at_unix_ms),
                metric=sample.metric,
                value=sample.value,
                tags=dict(sample.tags),
                # Metric registration metadata carried through from the device
                # (Task.md C-08) -- dropped at this boundary before, which was
                # the point of the reconcile.
                unit=sample.unit or None,
                metric_type=sample.metric_type or None,
            )
        )
    if batch.HasField("location") and (batch.location.lat or batch.location.lon):
        loc = batch.location
        recorded_at = (
            _ms_to_dt(loc.recorded_at_unix_ms) if loc.recorded_at_unix_ms else datetime.now(UTC)
        )
        session.add(
            TelemetrySample(
                device_id=device.id,
                recorded_at=recorded_at,
                metric="location",
                value=0.0,
                tags={
                    "lat": str(loc.lat),
                    "lon": str(loc.lon),
                    "accuracy_m": str(loc.accuracy_m),
                    "source": Location.Source.Name(loc.source),
                },
            )
        )
    await session.flush()


async def handle_log_upload_request(
    session: AsyncSession, device: Device, req: LogUploadRequest
) -> tuple[str, str, int]:
    """Creates the LogBundle/Backup row eagerly (optimistic -- there is no
    upload-complete callback in this proto version, see gateway/servicer.py)
    and returns (request_ref, presigned_put_url, expires_in_s) for the
    SignedUploadUrl response frame.
    """
    object_id = new_object_id()
    kind = "backup" if req.kind == LogUploadRequest.BACKUP else "log_bundle"
    key = object_key(kind, str(device.id), str(object_id))
    now = datetime.now(UTC)

    if req.kind == LogUploadRequest.BACKUP:
        session.add(
            Backup(
                id=object_id,
                device_id=device.id,
                storage_url=key,
                size_bytes=req.size_bytes_estimate,
                created_at=now,
            )
        )
    else:
        session.add(
            LogBundle(
                id=object_id,
                device_id=device.id,
                storage_url=key,
                size_bytes=req.size_bytes_estimate,
                uploaded_at=now,
                time_range_start=_ms_to_dt(req.time_range_start_unix_ms),
                time_range_end=_ms_to_dt(req.time_range_end_unix_ms),
            )
        )
    await session.flush()

    expires_in = 900
    return str(object_id), presigned_upload_url(key, expires_in=expires_in), expires_in


async def _evaluate_fault_alarms(session: AsyncSession, device: Device, fault: Fault) -> None:
    rules = (
        await session.execute(
            select(AlarmRule).where(
                AlarmRule.tenant_id == device.tenant_id, AlarmRule.enabled.is_(True)
            )
        )
    ).scalars().all()
    for rule in rules:
        cond = rule.condition or {}
        if cond.get("kind") != "fault_code":
            continue
        severity_filter = cond.get("severity")
        code_filter = cond.get("code")
        if severity_filter and severity_filter != fault.severity.value:
            continue
        if code_filter and code_filter != fault.code:
            continue
        session.add(
            Alarm(
                alarm_rule_id=rule.id,
                device_id=device.id,
                state=AlarmState.active,
                triggered_at=fault.raised_at,
                source_fault_id=fault.id,
            )
        )


async def handle_fault_event(session: AsyncSession, device: Device, event: FaultEvent) -> None:
    if event.kind == FaultEvent.CLEARED:
        code = event.fault_code_ref or event.code
        open_fault = (
            await session.execute(
                select(Fault)
                .where(Fault.device_id == device.id, Fault.code == code, Fault.cleared_at.is_(None))
                .order_by(Fault.raised_at.desc())
            )
        ).scalars().first()
        if open_fault:
            open_fault.cleared_at = _ms_to_dt(event.at_unix_ms)
        return

    fault = Fault(
        device_id=device.id,
        code=event.code,
        severity=_SEVERITY_MAP.get(event.severity, FaultSeverity.info),
        message=event.message,
        raised_at=_ms_to_dt(event.at_unix_ms),
    )
    session.add(fault)
    await session.flush()
    await _evaluate_fault_alarms(session, device, fault)


async def handle_agent_report(session: AsyncSession, device: Device, report_json: str) -> None:
    """Store the device's state dump (hardware inventory, services, network
    status) verbatim. The document shape is co-owned with
    Arches-Configuration; the web UI renders it defensively.

    Two fields are promoted onto columns (Task.md F-05): ``health_score``
    and ``spokes`` (the per-spoke status summary). They fit the report's
    JSON document precisely so the schema never needs a proto bump per
    field, but a fleet operator should be able to see a restarting spoke in
    a list without opening the raw document.
    """
    try:
        doc = json.loads(report_json)
    except json.JSONDecodeError:
        logger.warning("agent_report from device %s is not valid JSON; storing raw", device.id)
        device.reported = {"raw": report_json}
        return
    device.reported = doc
    if isinstance(doc, dict):
        score = doc.get("health_score")
        if isinstance(score, (int, float)):
            device.health_score = float(max(0.0, min(1.0, float(score))))
        spokes = doc.get("spokes")
        if isinstance(spokes, list):
            device.spoke_status = spokes
        elif isinstance(spokes, dict):
            device.spoke_status = spokes


async def handle_alarm_event(
    session: AsyncSession, device: Device, event: AlarmEvent
) -> None:
    """Apply one X.733 alarm action from the device (Task.md C-06).

    Upserts by (device, packed alarm_code) so RAISE/SEVERITY_CHANGE/ACK
    update the row the device is already aggregating instead of stacking
    duplicates, and CLEAR resolves it. The device's count/first/last-seen
    are stored, not recounted -- HQ holds the same fact the device holds.
    """

    code = int(event.alarm_id) & 0xFFFFFFFF
    domain, module, alarm_type, alarm_index = alarms_catalog.decode_alarm_code(code)
    now = datetime.now(UTC)
    first_seen = _ms_to_dt(event.first_seen_unix_ms) if event.first_seen_unix_ms else now
    last_seen = _ms_to_dt(event.last_seen_unix_ms) if event.last_seen_unix_ms else first_seen
    severity = _ALARM_SEVERITY_MAP.get(event.severity, FaultSeverity.info)
    correlated = [int(c) for c in event.correlated] or None

    row = (
        await session.execute(
            select(DeviceAlarm).where(
                DeviceAlarm.device_id == device.id, DeviceAlarm.alarm_code == code
            )
        )
    ).scalars().first()

    if event.action == AlarmEvent.CLEAR:
        if row is None:
            logger.warning("alarm CLEAR for unknown code %s on device %s", hex(code), device.id)
            return
        row.state = AlarmState.resolved
        row.resolved_at = last_seen
        row.acknowledged = row.acknowledged or event.acknowledged
        row.last_seen_at = last_seen
        if event.count:
            row.count = event.count
        return

    if row is None:
        row = DeviceAlarm(
            device_id=device.id,
            domain=domain,
            module=module,
            alarm_type=alarm_type,
            alarm_index=alarm_index,
            alarm_code=code,
            severity=severity,
            state=AlarmState.active,
            triggered_at=first_seen,
            owner=event.owner or None,
            additional_text=event.additional_text or None,
            count=event.count or None,
            acknowledged=event.acknowledged,
            needs_snapshot=event.needs_snapshot,
            first_seen_at=first_seen,
            last_seen_at=last_seen,
            correlated=correlated,
        )
        session.add(row)
        await session.flush()
        return

    # Existing row: severity-change and re-raise update it; ack marks it.
    if event.action == AlarmEvent.SEVERITY_CHANGE:
        row.severity = severity
    if event.count:
        row.count = event.count
    row.acknowledged = row.acknowledged or event.acknowledged
    row.needs_snapshot = row.needs_snapshot or event.needs_snapshot
    row.last_seen_at = max(row.last_seen_at or last_seen, last_seen)
    if row.first_seen_at is None:
        row.first_seen_at = first_seen
    if correlated:
        row.correlated = correlated
    if event.additional_text:
        row.additional_text = event.additional_text
    if event.owner:
        row.owner = event.owner
    if row.state == AlarmState.resolved and event.action == AlarmEvent.RAISE:
        # Re-raise of a resolved alarm reactivates it, like the device does.
        row.state = AlarmState.active
        row.resolved_at = None


async def handle_backup_status(
    session: AsyncSession, device: Device, status: BackupStatus
) -> None:
    """Record a backup-completion report (Task.md C-12).

    The Backup row was created eagerly with a size estimate when the
    SignedUploadUrl was issued; this report replaces the estimate with the
    archive's real name, size and checksum. If no row matches (upload never
    requested through the gateway, or HQ restarted), one is created.
    """
    now = datetime.now(UTC)
    created_at = (
        _ms_to_dt(status.created_at_unix_ms) if status.created_at_unix_ms else now
    )
    row = (
        await session.execute(
            select(Backup)
            .where(Backup.device_id == device.id, Backup.upload_completed_at.is_(None))
            .order_by(Backup.created_at.desc())
        )
    ).scalars().first()
    if row is None:
        row = Backup(
            device_id=device.id,
            storage_url=object_key("backup", str(device.id), str(new_object_id())),
            size_bytes=status.size_bytes or 0,
            created_at=created_at,
        )
        session.add(row)
        await session.flush()
    row.name = status.name or row.name
    if status.size_bytes:
        row.size_bytes = status.size_bytes
    row.checksum_sha256 = status.checksum_sha256 or row.checksum_sha256
    row.upload_completed_at = datetime.now(UTC)
    row.success = status.success


async def drain_pending_commands(session: AsyncSession, device_id: uuid.UUID) -> list[ServerFrame]:
    """Deliver queued PendingCommand rows to a connected device.

    The REST API and this gateway are separate deployables (no direct RPC
    between them), so a command an operator triggers via the API is written
    to pending_command and picked up here on the device's next
    heartbeat/connection -- ARCHITECTURE.md §2, PendingCommand docstring.
    Rows are marked delivered as they are converted, before the frames are
    actually flushed to the wire: delivery is at-most-once per connection
    and the device acks (CommandAck) for the durable outcome.
    """
    rows = (
        await session.execute(
            select(PendingCommand)
            .where(PendingCommand.device_id == device_id, PendingCommand.delivered_at.is_(None))
            .order_by(PendingCommand.created_at.asc())
            .limit(50)
        )
    ).scalars().all()

    frames: list[ServerFrame] = []
    now = datetime.now(UTC)
    for row in rows:
        command = Command(command_id=row.command_id)
        try:
            if row.kind == CommandKind.take_backup_now:
                command.take_backup_now.CopyFrom(TakeBackupNow())
            elif row.kind == CommandKind.restore:
                command.restore.CopyFrom(Restore(**row.payload))
            elif row.kind == CommandKind.factory_reset:
                command.factory_reset.CopyFrom(FactoryReset())
            elif row.kind == CommandKind.apply_update:
                command.apply_update.CopyFrom(ApplyUpdate(**row.payload))
            elif row.kind == CommandKind.reboot:
                command.reboot.CopyFrom(Reboot())
            elif row.kind == CommandKind.shutdown:
                command.shutdown.CopyFrom(Shutdown())
            elif row.kind == CommandKind.apply_config:
                # Task.md C-10: the signed push replaced the bare
                # ApplyConfig notification. The desired state travels on
                # the frame, HQ-signed, verified on device before apply.
                # A signing key that is unavailable degrades to the legacy
                # notification form so the operator's change is not
                # silently lost -- but it is logged, because an unverified
                # apply is the property this path exists to prevent.
                signed = await _signed_config_frame(session, device_id, row)
                row.delivered_at = now
                if signed is not None:
                    frames.append(signed)
                else:
                    command.apply_config.CopyFrom(
                        ApplyConfig(section=row.payload.get("section", ""))
                    )
                    frames.append(ServerFrame(command=command))
                continue
            else:
                logger.warning("pending command %s has unknown kind %s", row.command_id, row.kind)
                row.delivered_at = now
                continue
        except (TypeError, ValueError):
            logger.exception("pending command %s has malformed payload", row.command_id)
            row.delivered_at = now
            continue
        row.delivered_at = now
        frames.append(ServerFrame(command=command))
    return frames


async def _signed_config_frame(
    session: AsyncSession, device_id: uuid.UUID, row: PendingCommand
) -> ServerFrame | None:
    """Build the SignedConfig frame for an apply_config pending command.

    Loads the desired state HQ stores for the section, maps the section to
    the device daemon that owns it (see _SECTION_TO_DEVICE), serializes it
    as YAML (JSON is a YAML subset, but the explicit dump keeps key order
    and comments-free structure legible on the device's /pst viewer) and
    signs ``daemon|yaml`` with the fleet key (Task.md C-10). Returns None
    when signing is unavailable, which the caller turns into the legacy
    notification form.
    """
    import yaml

    section = row.payload.get("section", "")
    daemon = _SECTION_TO_DAEMON.get(section)
    if not daemon:
        logger.warning(
            "apply_config for unknown section %r; cannot map to a device daemon", section
        )
        return None
    from app.models.device_config import DeviceConfig

    cfg = (
        await session.execute(
            select(DeviceConfig).where(
                DeviceConfig.device_id == device_id, DeviceConfig.section == section
            )
        )
    ).scalar_one_or_none()
    if cfg is None or not cfg.config:
        return None
    yaml_text = yaml.safe_dump(cfg.config, default_flow_style=False, sort_keys=False)
    key = config_signing.get_config_signing_key()
    return ServerFrame(
        signed_config=SignedConfig(
            daemon=daemon,
            yaml=yaml_text,
            key_id=key.key_id,
            signature=key.sign_config(daemon, yaml_text),
        )
    )


async def handle_command_ack(
    session: AsyncSession, device: Device, command_id: str, success: bool, error: str
) -> None:
    if command_id.startswith("update:"):
        rollout_id = uuid.UUID(command_id.split(":", 2)[1])
        row = await session.get(
            UpdateRolloutDevice, {"rollout_id": rollout_id, "device_id": device.id}
        )
        if row is None:
            logger.warning("command_ack for unknown rollout row %s", command_id)
            return
        row.status = DeviceRolloutStatus.succeeded if success else DeviceRolloutStatus.failed
        row.applied_at = datetime.now(UTC)
        row.error = None if success else error

        siblings = (
            await session.execute(
                select(UpdateRolloutDevice).where(UpdateRolloutDevice.rollout_id == rollout_id)
            )
        ).scalars().all()
        terminal = (DeviceRolloutStatus.succeeded, DeviceRolloutStatus.failed)
        all_terminal = all(s.status in terminal for s in siblings)
        if all_terminal:
            rollout = await session.get(UpdateRollout, rollout_id)
            if rollout:
                rollout.status = RolloutStatus.completed
                rollout.completed_at = datetime.now(UTC)
    elif command_id.startswith("restore:"):
        backup_id = uuid.UUID(command_id.split(":", 2)[1])
        backup = await session.get(Backup, backup_id)
        if backup and success:
            backup.restored_at = datetime.now(UTC)
    else:
        logger.info("command_ack %s success=%s error=%s", command_id, success, error)
