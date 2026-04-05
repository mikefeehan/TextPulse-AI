from datetime import datetime

from pydantic import BaseModel


class VaultCategoryRead(BaseModel):
    id: str
    name: str
    emoji: str
    description: str
    count: int
    is_default: bool
    is_active: bool


class VaultCategoryCreate(BaseModel):
    name: str
    emoji: str
    description: str


class VaultMessageCard(BaseModel):
    message_id: str
    text: str
    timestamp: datetime
    reasoning: str
    confidence: float
    context_before: list[str]
    context_after: list[str]


class VaultCategoryDetail(BaseModel):
    category: VaultCategoryRead
    stats: dict[str, str | int | float]
    messages: list[VaultMessageCard]
