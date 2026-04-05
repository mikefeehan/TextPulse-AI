from __future__ import annotations

import json
from pathlib import Path
from datetime import UTC, datetime

from app.models.entities import SenderType
from app.services.parsers.base import ParsedMessage

try:
    import ijson
except ImportError:  # pragma: no cover - optional streaming dependency
    ijson = None


def parse_telegram_export(content: str, contact_identifier: str | None = None) -> list[ParsedMessage]:
    payload = json.loads(content)
    return _parse_telegram_payload(payload, contact_identifier=contact_identifier)


def parse_telegram_file(file_path: str, contact_identifier: str | None = None) -> list[ParsedMessage]:
    if ijson is not None:
        stream_result = _parse_telegram_stream(file_path, contact_identifier=contact_identifier)
        if stream_result is not None:
            return stream_result
    with Path(file_path).open("r", encoding="utf-8", errors="ignore") as handle:
        payload = json.load(handle)
    return _parse_telegram_payload(payload, contact_identifier=contact_identifier)


def _parse_telegram_payload(payload: dict | list, contact_identifier: str | None = None) -> list[ParsedMessage]:
    rows = payload.get("messages", []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    messages: list[ParsedMessage] = []
    for index, row in enumerate(rows):
        parsed = _parse_telegram_row(row, index=index, contact_identifier=contact_identifier)
        if parsed is None:
            continue
        messages.append(parsed)
    return messages


def _parse_telegram_stream(file_path: str, contact_identifier: str | None = None) -> list[ParsedMessage] | None:
    root_char = _peek_json_root(file_path)
    if root_char not in {"{", "["}:
        return None

    prefix = "messages.item" if root_char == "{" else "item"
    messages: list[ParsedMessage] = []
    with Path(file_path).open("rb") as handle:
        for index, row in enumerate(ijson.items(handle, prefix)):
            parsed = _parse_telegram_row(row, index=index, contact_identifier=contact_identifier)
            if parsed is not None:
                messages.append(parsed)
    return messages


def _parse_telegram_row(
    row: dict,
    *,
    index: int,
    contact_identifier: str | None = None,
) -> ParsedMessage | None:
    text = row.get("text")
    if isinstance(text, list):
        text = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in text)
    if not text:
        return None
    from_name = str(row.get("from", "")).strip()
    sender = SenderType.CONTACT
    if contact_identifier and contact_identifier.lower() not in from_name.lower():
        sender = SenderType.USER

    timestamp = _parse_datetime(str(row.get("date")))
    return ParsedMessage(
        canonical_id=str(row.get("id", f"tg-{index}")),
        sender=sender,
        text=text,
        timestamp=timestamp,
    ).normalize()


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def _peek_json_root(file_path: str) -> str | None:
    with Path(file_path).open("r", encoding="utf-8", errors="ignore") as handle:
        while True:
            char = handle.read(1)
            if not char:
                return None
            if not char.isspace():
                return char
