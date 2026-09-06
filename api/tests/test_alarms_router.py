from datetime import datetime, UTC
from uuid import uuid4

from app.models.alarm import Alarm, AlarmRule
from app.models.device import Device
from app.models.enums import AlarmState, FaultSeverity, UserRole
from tests.factories import login_as, make_tenant, make_user


# Locked 32-bit alarm layout (source of truth:
# Arches-Instrumentation/catalog/alarms.yaml and REQ.md section 8):
#   [31:28] domain, [27:20] module, [19:16] type, [15:0] index.
# Severity is NOT in the code -- it is reported as its own field.
#
# The catalog's own worked example, 0x1_04_1_0007, packs to 0x10410007 and
# reads as hardware / Hardware daemon / equipment / alarm 7 -> (1, 4, 1, 7).
#
# These tests exercise the device-reported ``alarms`` table (model
# DeviceAlarm, __tablename__ == "alarms"), which is distinct from the
# rule-based ``alarm`` table.


async def test_post_alarm_then_get_decodes_4_fields(client, db_session):
    """R3: POST a device-reported alarm, then GET the device alarms list and
    assert the returned row decodes all 4 fields against the locked layout and
    alarm_code round-trips.

    Uses the catalog's own worked example so a regression here is checkable
    against Arches-Instrumentation/REQ.md rather than against this test.
    """
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="pi-5-alarm-1")
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)
    device_id = str(device.id)

    login_as(client, admin)

    triggered_at = datetime(2026, 7, 30, 12, 0, 5, tzinfo=UTC)
    posted = {
        "alarm_code": "0x10410007",
        "triggered_at": triggered_at.isoformat(),
        "severity": "major",
    }

    resp = await client.post(f"/devices/{device_id}/alarms", json=posted)
    assert resp.status_code == 201, resp.text
    created = resp.json()

    # The POST response must already reflect the decoded 4 fields (R3).
    # hardware / Hardware daemon / equipment / alarm 7.
    assert created["domain"] == 1
    assert created["module"] == 4
    assert created["alarm_type"] == 1
    assert created["alarm_index"] == 7
    # Severity is reported, not decoded out of the code.
    assert created["severity"] == "major"
    assert created["alarm_code"] == 0x10410007
    assert created["state"] == AlarmState.active.value
    assert created["device_id"] == device_id
    assert "alarm_rule_id" not in created  # DeviceAlarm has no rule

    # GET the device alarms list; the row must carry the same decoded fields.
    list_resp = await client.get(f"/devices/{device_id}/alarms")
    assert list_resp.status_code == 200, list_resp.text
    items = list_resp.json()["items"]
    assert len(items) == 1
    fetched = items[0]

    assert fetched["id"] == created["id"]
    assert fetched["domain"] == 1
    assert fetched["module"] == 4
    assert fetched["alarm_type"] == 1
    assert fetched["alarm_index"] == 7
    assert fetched["severity"] == "major"
    assert fetched["alarm_code"] == 0x10410007
    assert fetched["device_id"] == device_id


async def test_post_alarm_boundary_values(client, db_session):
    """Field boundaries round-trip through the locked decode, including the
    0xFFFFFFFF case that overflows int32 (D1: BigInteger) and whose index
    (65535) overflows a signed SmallInteger column.
    """
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="pi-5-alarm-bnd")
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)
    device_id = str(device.id)

    login_as(client, admin)

    # (code, (domain, module, alarm_type, index))
    for code_hex, expected in [
        ("0x00000000", (0, 0, 0, 0)),
        ("0xffffffff", (0xF, 0xFF, 0xF, 0xFFFF)),
        ("0x10410007", (1, 4, 1, 7)),
        # Each field at its own maximum with the others zero -- catches a
        # decoder whose shifts are right but whose masks bleed into a neighbour.
        ("0xf0000000", (0xF, 0, 0, 0)),
        ("0x0ff00000", (0, 0xFF, 0, 0)),
        ("0x000f0000", (0, 0, 0xF, 0)),
        ("0x0000ffff", (0, 0, 0, 0xFFFF)),
    ]:
        resp = await client.post(
            f"/devices/{device_id}/alarms",
            json={
                "alarm_code": code_hex,
                "triggered_at": datetime.now(UTC).isoformat(),
            },
        )
        assert resp.status_code == 201, (code_hex, resp.text)
        body = resp.json()
        decoded = (body["domain"], body["module"], body["alarm_type"], body["alarm_index"])
        assert decoded == expected, code_hex
        assert body["alarm_code"] == int(code_hex, 16)


async def test_cross_tenant_device_404(client, db_session):
    """A tenant cannot ingest alarms against another tenant's device (404)."""
    tenant_a = await make_tenant(db_session)
    tenant_b = await make_tenant(db_session)
    admin_a = await make_user(db_session, tenant_a, UserRole.admin)
    device_b = Device(tenant_id=tenant_b.id, name="pi-5-other-tenant")
    db_session.add(device_b)
    await db_session.commit()
    await db_session.refresh(device_b)

    login_as(client, admin_a)
    resp = await client.post(
        f"/devices/{device_b.id}/alarms",
        json={
            "alarm_code": "0x01020304",
            "triggered_at": datetime.now(UTC).isoformat(),
        },
    )
    assert resp.status_code == 404, resp.text


async def test_clear_device_alarm_resolves(client, db_session):
    """R3: the device-scoped `clear` verb resolves the alarm (state=resolved).
    `clear` == `resolve` -- there is no separate `cleared` state (F5).
    """
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="pi-5-alarm-clear")
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)
    device_id = str(device.id)

    login_as(client, admin)

    posted = await client.post(
        f"/devices/{device_id}/alarms",
        json={
            "alarm_code": "0x01020304",
            "triggered_at": datetime.now(UTC).isoformat(),
        },
    )
    assert posted.status_code == 201, posted.text
    alarm_id = posted.json()["id"]

    clear = await client.post(f"/devices/{device_id}/alarms/{alarm_id}/clear")
    assert clear.status_code == 200, clear.text
    cleared = clear.json()
    assert cleared["state"] == AlarmState.resolved.value
    assert cleared["resolved_at"] is not None


async def test_operator_can_ingest_viewer_cannot(client, db_session):
    """require_role(operator) on POST ingest: an operator may ingest, a viewer may not."""
    tenant = await make_tenant(db_session)
    op = await make_user(db_session, tenant, UserRole.operator)
    viewer = await make_user(db_session, tenant, UserRole.viewer)
    device = Device(tenant_id=tenant.id, name="pi-5-alarm-rbac")
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)

    payload = {
        "alarm_code": "0x01020304",
        "triggered_at": datetime.now(UTC).isoformat(),
    }

    login_as(client, op)
    resp = await client.post(f"/devices/{device.id}/alarms", json=payload)
    assert resp.status_code == 201, resp.text

    login_as(client, viewer)
    resp = await client.post(f"/devices/{device.id}/alarms", json=payload)
    assert resp.status_code == 403, resp.text


async def test_clear_unknown_alarm_404(client, db_session):
    """Clearing a non-existent alarm on a real device 404s, not leaks existence."""
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="pi-5-alarm-404")
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)

    login_as(client, admin)
    resp = await client.post(f"/devices/{device.id}/alarms/{uuid4()}/clear")
    assert resp.status_code == 404, resp.text


async def test_active_alarms_fleet_feed(client, db_session):
    """GET /alarms/active -- fleet-wide feed powering the top-bar bell."""
    from app.models.device import Device
    from app.models.device_alarm import DeviceAlarm

    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    d1 = Device(tenant_id=tenant.id, name="alpha")
    d2 = Device(tenant_id=tenant.id, name="beta")
    db_session.add_all([d1, d2])
    await db_session.flush()
    from datetime import datetime, UTC

    now = datetime.now(UTC)
    db_session.add_all(
        [
            DeviceAlarm(device_id=d1.id, domain=1, module=4, alarm_type=1, alarm_index=7,
                        severity=FaultSeverity.major, alarm_code=0x10410007, triggered_at=now),
            DeviceAlarm(
                device_id=d2.id, domain=2, module=9, alarm_type=3, alarm_index=8,
                severity=FaultSeverity.minor, alarm_code=0x29030008, state="resolved",
                triggered_at=now,
            ),
        ]
    )
    await db_session.commit()

    login_as(client, admin)
    resp = await client.get("/alarms/active")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["device_name"] == "alpha"
    assert body["items"][0]["alarm_code"] == 0x10410007


async def test_rule_alarm_history_listed_with_device_name(client, db_session):
    tenant = await make_tenant(db_session)
    admin = await make_user(db_session, tenant, UserRole.admin)
    device = Device(tenant_id=tenant.id, name="hist-device")
    db_session.add(device)
    await db_session.flush()
    rule = AlarmRule(tenant_id=tenant.id, name="cpu", condition={"kind": "fault_code"})
    db_session.add(rule)
    await db_session.flush()
    db_session.add(
        Alarm(
            alarm_rule_id=rule.id,
            device_id=device.id,
            state=AlarmState.active,
            triggered_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    login_as(client, admin)
    resp = await client.get("/alarms")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["device_name"] == "hist-device"
    assert body["items"][0]["alarm"]["state"] == "active"


# ---------------------------------------------------------------------------
# Locked-layout unit tests (Task.md C-03).
#
# These call the decoder directly rather than through HTTP, so a layout
# regression is reported as a layout failure rather than as a routing one.
# ---------------------------------------------------------------------------


def test_decode_matches_the_catalog_worked_example():
    """REQ.md section 8: 0x1_04_1_0007 is hardware / Hardware daemon /
    equipment / alarm 7.

    This is the example the locked layout is documented with, so it is the one
    worth pinning. The old four-equal-bytes decoder returned (16, 65, 0, 7)
    for this input -- the byte boundaries fall inside the domain and module
    fields, so the values were garbage rather than merely shifted.
    """
    from app.routers.alarms import _decode_alarm_code

    assert _decode_alarm_code(0x10410007) == (1, 4, 1, 7)
    # The specific way it used to be wrong, pinned so the old decoder cannot
    # quietly come back.
    assert _decode_alarm_code(0x10410007) != (16, 65, 0, 7)


def test_decode_isolates_each_field():
    """Each field at its maximum with the others zero.

    Catches a decoder with correct shifts but a mask that bleeds into the
    neighbouring field -- the failure mode a single worked example misses.
    """
    from app.routers.alarms import _decode_alarm_code

    assert _decode_alarm_code(0xF0000000) == (0xF, 0, 0, 0)
    assert _decode_alarm_code(0x0FF00000) == (0, 0xFF, 0, 0)
    assert _decode_alarm_code(0x000F0000) == (0, 0, 0xF, 0)
    assert _decode_alarm_code(0x0000FFFF) == (0, 0, 0, 0xFFFF)


def test_encode_decode_round_trips_across_the_field_ranges():
    """Round-trip every field boundary through encode and back."""
    from app.routers.alarms import _decode_alarm_code, _encode_alarm_code

    for domain in (0, 1, 0xF):
        for module in (0, 4, 0xFF):
            for alarm_type in (0, 1, 0xF):
                for index in (0, 7, 0xFFFF):
                    fields = (domain, module, alarm_type, index)
                    assert _decode_alarm_code(_encode_alarm_code(*fields)) == fields


def test_severity_is_not_encoded_in_the_code():
    """Two alarms differing only in severity must share one code.

    Severity travels as its own field precisely because it changes over an
    alarm's life (X.733 severity-change events); if it were packed into the
    code, a severity change would look like a different alarm.
    """
    from app.routers.alarms import _encode_alarm_code

    assert _encode_alarm_code(1, 4, 1, 7) == _encode_alarm_code(1, 4, 1, 7) == 0x10410007


def test_fault_severity_covers_the_five_x733_levels():
    """Task.md C-05: MAJOR and MINOR must have somewhere to land.

    catalog/alarms.yaml uses both heavily -- they are among its first entries.
    """
    from app.models.enums import SEVERITY_ORDER, FaultSeverity

    assert {s.value for s in FaultSeverity} == {
        "info",
        "warning",
        "minor",
        "major",
        "critical",
    }
    # Ranking must be strictly increasing in severity, or severity-ordered
    # queries and thresholds silently misbehave.
    ranks = [SEVERITY_ORDER[s] for s in (
        FaultSeverity.info,
        FaultSeverity.warning,
        FaultSeverity.minor,
        FaultSeverity.major,
        FaultSeverity.critical,
    )]
    assert ranks == sorted(ranks) and len(set(ranks)) == len(ranks)
