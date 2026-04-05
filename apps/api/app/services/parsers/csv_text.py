from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path
import re
from datetime import UTC, datetime
from typing import Iterable

from app.models.entities import SenderType
from app.services.parsers.base import ParsedMessage
from app.services.parsers.whatsapp import parse_whatsapp_export, parse_whatsapp_file

TIMESTAMP_FIELDS = ("timestamp", "date", "sent_at", "time")
SENDER_FIELDS = ("sender", "from", "author", "name")
TEXT_FIELDS = ("message", "text", "body", "content")


def parse_csv_export(content: str, contact_identifier: str | None = None) -> list[ParsedMessage]:
    reader = csv.DictReader(io.StringIO(content))
    return _parse_csv_rows(reader, contact_identifier=contact_identifier)


def parse_csv_file(file_path: str, contact_identifier: str | None = None) -> list[ParsedMessage]:
    with Path(file_path).open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.DictReader(handle)
        return _parse_csv_rows(reader, contact_identifier=contact_identifier)


def _parse_csv_rows(reader: csv.DictReader, contact_identifier: str | None = None) -> list[ParsedMessage]:
    messages: list[ParsedMessage] = []
    for index, row in enumerate(reader):
        timestamp_text = _first_match(row, TIMESTAMP_FIELDS)
        sender_text = _first_match(row, SENDER_FIELDS) or ""
        body = _first_match(row, TEXT_FIELDS) or ""
        if not timestamp_text or not body:
            continue
        timestamp = _parse_datetime(timestamp_text)
        sender = SenderType.CONTACT
        if contact_identifier and contact_identifier.lower() not in sender_text.lower():
            sender = SenderType.USER
        messages.append(
            ParsedMessage(
                canonical_id=f"csv-{index}-{hashlib.sha1(body.encode('utf-8')).hexdigest()[:12]}",
                sender=sender,
                text=body,
                timestamp=timestamp,
            ).normalize()
        )
    return messages


def parse_text_blob(content: str, contact_identifier: str | None = None) -> list[ParsedMessage]:
    whatsapp_messages = parse_whatsapp_export(content, contact_identifier=contact_identifier)
    if whatsapp_messages:
        return whatsapp_messages
    return _parse_text_lines(content.splitlines(), contact_identifier=contact_identifier)


def parse_text_file(file_path: str, contact_identifier: str | None = None) -> list[ParsedMessage]:
    whatsapp_messages = parse_whatsapp_file(file_path, contact_identifier=contact_identifier)
    if whatsapp_messages:
        return whatsapp_messages

    with Path(file_path).open("r", encoding="utf-8", errors="ignore") as handle:
        return _parse_text_lines(handle, contact_identifier=contact_identifier)


def _parse_text_lines(lines: Iterable[str], contact_identifier: str | None = None) -> list[ParsedMessage]:
    line_pattern = re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?)\s*[|-]\s*(?P<sender>[^:]+):\s*(?P<text>.+)$"
    )
    messages: list[ParsedMessage] = []
    for index, line in enumerate(lines):
        match = line_pattern.match(line.strip())
        if match:
            sender_name = match.group("sender")
            sender = SenderType.CONTACT
            if contact_identifier and contact_identifier.lower() not in sender_name.lower():
                sender = SenderType.USER
            messages.append(
                ParsedMessage(
                    canonical_id=f"text-{index}",
                    sender=sender,
                    text=match.group("text"),
                    timestamp=_parse_datetime(match.group("timestamp")),
                ).normalize()
            )
        elif line.strip():
            sender = SenderType.CONTACT if index % 2 == 0 else SenderType.USER
            messages.append(
                ParsedMessage(
                    canonical_id=f"text-fallback-{index}",
                    sender=sender,
                    text=line.strip(),
                    timestamp=datetime.now(UTC),
                ).normalize()
            )
    return messages


def _first_match(row: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    lowered = {key.lower(): value for key, value in row.items()}
    for candidate in candidates:
        if candidate in lowered and lowered[candidate]:
            return lowered[candidate]
    return None


def _parse_datetime(value: str) -> datetime:
    candidates = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%y %H:%M:%S",
        "%m/%d/%y %H:%M",
    )
    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return datetime.now(UTC)
