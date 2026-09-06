from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

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


class ActiveAlarmListOut(BaseModel):
    count: int
    items: list[ActiveAlarmOut]
