from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import AIQualityMode, ORMModel


class QAMessageRead(ORMModel):
    id: str
    role: str
    content: str
    created_at: datetime


class QASessionRead(ORMModel):
    id: str
    created_at: datetime
    messages: list[QAMessageRead] = Field(default_factory=list)


class QASessionCreateResponse(BaseModel):
    session: QASessionRead


class QAUserMessageRequest(BaseModel):
    content: str = Field(min_length=1)
    quality_mode: AIQualityMode | None = None


class QAReply(BaseModel):
    session_id: str
    answer: str
    supporting_examples: list[str]
    cited_messages: list[str]
