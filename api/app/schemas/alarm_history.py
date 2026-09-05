"""Fleet-wide rule-based alarm history rows for the Alerts page."""


from pydantic import BaseModel

from app.schemas.alarm import AlarmOut
from app.schemas.common import Page


class AlarmHistoryItem(BaseModel):
    alarm: AlarmOut
    device_name: str


class AlarmHistoryListOut(BaseModel):
    items: list[AlarmHistoryItem]
    page: Page
