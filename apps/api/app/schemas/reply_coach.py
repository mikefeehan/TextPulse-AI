from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import AIQualityMode, ORMModel


class ReplyCoachRequest(BaseModel):
    incoming_message: str = Field(min_length=1)
    quality_mode: AIQualityMode | None = None


class ReplyOption(BaseModel):
    label: str
    tone: str
    message: str
    what_it_signals: str
    likely_reaction: str


class ReplyCoachResponse(ORMModel):
    id: str
    incoming_message: str
    subtext_analysis: str
    reply_options: list[ReplyOption]
    danger_zones: list[str]
    timing_recommendation: str
    escalation_guidance: str
    created_at: datetime
