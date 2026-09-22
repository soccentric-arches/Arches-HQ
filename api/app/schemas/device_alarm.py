from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AlarmState, FaultSeverity
from app.schemas.common import Page


class DeviceAlarmIn(BaseModel):
    """Device-reported alarm ingest payload (R3).

    ``alarm_code`` is the packed 32-bit alarm code as a hex string, e.g.
    ``"0x10410007"``. The server decodes it into domain / module / alarm_type /
    index using the locked layout documented on the router and in
    ``Arches-Instrumentation/catalog/alarms.yaml``.

    ``severity`` is reported separately rather than extracted from the code --
    an alarm's severity can change over its life. It defaults to ``warning``
    when omitted; once HQ consumes the alarm catalog (Task.md C-07) the default
    should come from the catalog entry for this alarm id instead.

    ``triggered_at`` is the device-side timestamp, stored verbatim.
    """

    alarm_code: str
    triggered_at: datetime
    severity: FaultSeverity = FaultSeverity.warning


class DeviceAlarmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_id: UUID
    domain: int
    module: int
    alarm_type: int
    alarm_index: int
    severity: FaultSeverity
    alarm_code: int
    state: AlarmState
    triggered_at: datetime
    resolved_at: datetime | None

    # AlarmEvent transport fields (Task.md C-06).
    owner: str | None = None
    additional_text: str | None
    count: int | None
    acknowledged: bool
    needs_snapshot: bool
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    correlated: list[int] | None

    # Catalog fields joined at render time (Task.md C-07): the vendored
    # catalog supplies symbolic name, causes, description, escalation and
    # auto-clear policy so alarms render without hardcoding. Empty dict when
    # the code is not in the catalog.
    catalog: dict = Field(default_factory=dict)


class DeviceAlarmListOut(BaseModel):
    items: list[DeviceAlarmOut]
    page: Page


class ActiveAlarmOut(BaseModel):
    """Fleet-wide active alarm for the top-bar bell / overview page."""

    id: UUID
    device_id: UUID
    device_name: str
    domain: int
    module: int
    alarm_type: int
    alarm_index: int
    severity: FaultSeverity
    alarm_code: int
    state: AlarmState
    triggered_at: datetime
    # Catalog symbolic name (C-07); falls back to empty for unknown codes.
    name: str = ""
    # X.733 correlated notification ids (C-06) so the UI can group
    # escalation chains instead of showing N flat rows (F-08).
    correlated: list[int] = Field(default_factory=list)


class ActiveAlarmListOut(BaseModel):
    count: int
    items: list[ActiveAlarmOut]
