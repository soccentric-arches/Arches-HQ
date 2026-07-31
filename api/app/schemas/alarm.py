from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import AlarmState
from app.schemas.common import Page


class AlarmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alarm_rule_id: UUID | None
    device_id: UUID
    state: AlarmState
    triggered_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    # 4-byte alarm scheme fields (device-reported alarms). Null for rule-based
    # alarms that pre-date the ingest path.
    major_id: int | None
    sub_section: int | None
    fault_type: int | None
    severity: int | None
    alarm_code: int | None


class AlarmListOut(BaseModel):
    items: list[AlarmOut]
    page: Page


class AlarmIn(BaseModel):
    """Device-reported alarm ingest payload (R3).

    `alarm_code` is the packed 4-byte alarm code as a hex string, e.g.
    "0x01020304". The server decodes it into major_id / sub_section /
    fault_type / severity using the byte order documented on the router
    (byte 0 = major_id, byte 1 = sub_section, byte 2 = fault_type,
    byte 3 = severity -- big-endian, byte 0 most significant).
    `triggered_at` is the device-side timestamp, stored verbatim.
    """

    alarm_code: str
    triggered_at: datetime


class AlarmRuleCreate(BaseModel):
    name: str
    condition: dict
    notify_channels: dict = {}
    enabled: bool = True


class AlarmRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    condition: dict
    notify_channels: dict
    enabled: bool