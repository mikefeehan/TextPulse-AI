from __future__ import annotations

import json
from pathlib import Path

from app.models import ImportPlatform
from app.services.parsers import parse_messages


def test_parse_telegram_file_path(tmp_path: Path) -> None:
    payload = {
        "messages": [
            {"id": 1, "from": "Alex", "date": "2026-03-18T18:00:00Z", "text": "Hey"},
            {"id": 2, "from": "Me", "date": "2026-03-18T18:05:00Z", "text": ["See ", {"text": "you"}]},
        ]
    }
    export_path = tmp_path / "telegram.json"
    export_path.write_text(json.dumps(payload), encoding="utf-8")

    messages = parse_messages(
        source_platform=ImportPlatform.TELEGRAM,
        file_path=str(export_path),
        contact_identifier="Alex",
    )

    assert len(messages) == 2
    assert messages[0].sender.value == "contact"
    assert messages[1].sender.value == "user"
    assert messages[1].text == "See you"


def test_parse_instagram_file_path(tmp_path: Path) -> None:
    payload = {
        "messages": [
            {"sender_name": "Me", "timestamp_ms": 1710000001000, "content": "Newest"},
            {"sender_name": "Alex", "timestamp_ms": 1710000000000, "content": "Older"},
        ]
    }
    export_path = tmp_path / "instagram.json"
    export_path.write_text(json.dumps(payload), encoding="utf-8")

    messages = parse_messages(
        source_platform=ImportPlatform.INSTAGRAM,
        file_path=str(export_path),
        contact_identifier="Alex",
    )

    assert len(messages) == 2
    assert messages[0].text == "Older"
    assert messages[1].text == "Newest"


def test_parse_android_sms_file_path(tmp_path: Path) -> None:
    payload = """
    <smses count="2">
      <sms protocol="0" address="+15551230000" date="1710000000000" body="From Alex" />
      <sms protocol="0" address="+15557654321" date="1710000600000" body="From me" />
    </smses>
    """.strip()
    export_path = tmp_path / "messages.xml"
    export_path.write_text(payload, encoding="utf-8")

    messages = parse_messages(
        source_platform=ImportPlatform.ANDROID_SMS,
        file_path=str(export_path),
        contact_identifier="+15551230000",
    )

    assert len(messages) == 2
    assert messages[0].sender.value == "contact"
    assert messages[1].sender.value == "user"
