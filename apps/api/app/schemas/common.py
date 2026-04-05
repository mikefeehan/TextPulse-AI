from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AIQualityMode(str, Enum):
    CHEAP = "cheap"
    BALANCED = "balanced"
    PREMIUM = "premium"


class DateRangeSummary(BaseModel):
    start: datetime | None
    end: datetime | None


class MetricExample(BaseModel):
    message_id: str
    text: str
    timestamp: datetime
    note: str
