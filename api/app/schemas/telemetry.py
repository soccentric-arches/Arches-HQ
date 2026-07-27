from datetime import datetime

from pydantic import BaseModel


class TelemetryPointOut(BaseModel):
    recorded_at: datetime
    value: float
