from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.models.entities import MessageType, SenderType


@dataclass(slots=True)
class ParsedMessage:
    canonical_id: str
    sender: SenderType
    text: str
    timestamp: datetime
    message_type: MessageType = MessageType.TEXT
    metadata_json: dict = field(default_factory=dict)

    def normalize(self) -> "ParsedMessage":
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=UTC)
        self.text = self.text.strip()
        return self
