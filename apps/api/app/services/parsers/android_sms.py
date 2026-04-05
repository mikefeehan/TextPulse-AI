from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from app.models.entities import SenderType
from app.services.parsers.base import ParsedMessage


def parse_android_sms_export(content: str, contact_identifier: str | None = None) -> list[ParsedMessage]:
    root = ET.fromstring(content)
    messages: list[ParsedMessage] = []
    for row in root.findall(".//sms"):
        parsed = _parse_sms_element(row.attrib, contact_identifier=contact_identifier)
        if parsed is None:
            continue
        messages.append(parsed)
    return messages


def parse_android_sms_file(file_path: str, contact_identifier: str | None = None) -> list[ParsedMessage]:
    messages: list[ParsedMessage] = []
    for _, element in ET.iterparse(file_path, events=("end",)):
        if element.tag != "sms":
            continue
        parsed = _parse_sms_element(element.attrib, contact_identifier=contact_identifier)
        if parsed is not None:
            messages.append(parsed)
        element.clear()
    return messages


def _parse_sms_element(
    attrib: dict[str, str],
    *,
    contact_identifier: str | None = None,
) -> ParsedMessage | None:
    address = attrib.get("address", "")
    sender = SenderType.CONTACT if not contact_identifier or contact_identifier.lower() in address.lower() else SenderType.USER
    timestamp = datetime.fromtimestamp(int(attrib.get("date", "0")) / 1000, tz=UTC)
    body = attrib.get("body", "").strip()
    if not body:
        return None
    return ParsedMessage(
        canonical_id=attrib.get("protocol", "") + "-" + attrib.get("date", ""),
        sender=sender,
        text=body,
        timestamp=timestamp,
    ).normalize()
