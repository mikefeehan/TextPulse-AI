from __future__ import annotations

import hashlib
from pathlib import Path
import re
from datetime import UTC, datetime
from typing import Iterable

from app.models.entities import SenderType
from app.services.parsers.base import ParsedMessage

PATTERNS = [
    re.compile(
        r"^\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}), (?P<time>\d{1,2}:\d{2}(?::\d{2})?)\] (?P<name>[^:]+): (?P<message>.+)$"
    ),
    re.compile(
        r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}), (?P<time>\d{1,2}:\d{2}(?::\d{2})?) - (?P<name>[^:]+): (?P<message>.+)$"
    ),
]


def parse_whatsapp_export(content: str, contact_identifier: str | None = None) -> list[ParsedMessage]:
    return _parse_whatsapp_lines(content.splitlines(), contact_identifier=contact_identifier)


def parse_whatsapp_file(file_path: str, contact_identifier: str | None = None) -> list[ParsedMessage]:
    with Path(file_path).open("r", encoding="utf-8", errors="ignore") as handle:
        return _parse_whatsapp_lines(handle, contact_identifier=contact_identifier)


def _parse_whatsapp_lines(lines: Iterable[str], contact_identifier: str | None = None) -> list[ParsedMessage]:
    messages: list[ParsedMessage] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        match = None
        for pattern in PATTERNS:
            match = pattern.match(stripped)
            if match:
                break
        if not match:
            if messages:
                messages[-1].text += f"\n{stripped}"
            continue

        parsed_date = _parse_datetime(match.group("date"), match.group("time"))
        name = match.group("name").strip()
        sender = SenderType.CONTACT
        if contact_identifier and contact_identifier.lower() not in name.lower():
            sender = SenderType.USER

        digest = hashlib.sha1(stripped.encode("utf-8")).hexdigest()
        messages.append(
            ParsedMessage(
                canonical_id=f"wa-{digest}",
                sender=sender,
                text=match.group("message"),
                timestamp=parsed_date,
            ).normalize()
        )
    return messages


def _parse_datetime(date_text: str, time_text: str) -> datetime:
    for fmt in ("%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%m/%d/%y %H:%M", "%m/%d/%Y %H:%M"):
        try:
            return datetime.strptime(f"{date_text} {time_text}", fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return datetime.now(UTC)
