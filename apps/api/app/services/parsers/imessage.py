from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.models.entities import MessageType, SenderType
from app.services.parsers.base import ParsedMessage
from app.services.parsers.ios_backup import extracted_chat_db

APPLE_EPOCH = 978307200
REACTION_TYPES = {
    2000: "loved",
    2001: "liked",
    2002: "disliked",
    2003: "laughed",
    2004: "emphasized",
    2005: "questioned",
}


@dataclass(slots=True)
class IMessageContactCandidate:
    identifier: str
    label: str
    total_messages: int
    sent_messages: int
    received_messages: int
    latest_message_at: datetime | None


def parse_imessage_db(file_path: str, contact_identifier: str | None = None) -> list[ParsedMessage]:
    with extracted_chat_db(file_path) as extracted:
        connection = sqlite3.connect(extracted.chat_db_path)
        connection.row_factory = sqlite3.Row

        try:
            if contact_identifier:
                rows = connection.execute(
                    _direct_chat_messages_query(), {"contact_identifier": contact_identifier}
                ).fetchall()
            else:
                rows = connection.execute(_all_messages_query()).fetchall()
        finally:
            connection.close()

    parsed: list[ParsedMessage] = []
    for row in rows:
        message_text = row["message_body"] or ""
        associated_type = int(row["associated_message_type"] or 0)
        message_type = MessageType.TEXT
        if associated_type in REACTION_TYPES:
            message_type = MessageType.REACTION
            message_text = f"{REACTION_TYPES[associated_type]}: {message_text}".strip()
        if not message_text and message_type != MessageType.REACTION:
            continue
        parsed.append(
            ParsedMessage(
                canonical_id=row["guid"] or f"imessage-{row['ROWID']}",
                sender=SenderType.USER if row["is_from_me"] else SenderType.CONTACT,
                text=message_text,
                timestamp=_apple_to_datetime(int(row["date"] or 0)),
                message_type=message_type,
                metadata_json={
                    "associated_message_type": associated_type,
                    "associated_message_guid": row["associated_message_guid"],
                    "sender_identifier": row["sender_identifier"],
                },
            ).normalize()
        )
    return parsed


def discover_imessage_contacts(file_path: str, limit: int = 20) -> list[IMessageContactCandidate]:
    with extracted_chat_db(file_path) as extracted:
        return _discover_imessage_contacts_from_db(extracted.chat_db_path, limit)


def _discover_imessage_contacts_from_db(database_path: Path, limit: int) -> list[IMessageContactCandidate]:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row

    query = """
    with direct_chats as (
        select
            c.ROWID as chat_id,
            max(h.id) as identifier,
            coalesce(nullif(c.display_name, ''), max(h.id), c.chat_identifier, 'Unknown') as label
        from chat c
        join chat_handle_join chj on chj.chat_id = c.ROWID
        join handle h on h.ROWID = chj.handle_id
        group by c.ROWID, c.display_name, c.chat_identifier
        having count(distinct h.id) = 1
    )
    select
        dc.identifier,
        dc.label,
        count(m.ROWID) as total_messages,
        sum(case when coalesce(m.is_from_me, 0) = 1 then 1 else 0 end) as sent_messages,
        sum(case when coalesce(m.is_from_me, 0) = 0 then 1 else 0 end) as received_messages,
        max(coalesce(m.date, 0)) as latest_date
    from direct_chats dc
    join chat_message_join cmj on cmj.chat_id = dc.chat_id
    join message m on m.ROWID = cmj.message_id
    group by dc.identifier, dc.label
    order by total_messages desc
    limit :limit
    """

    try:
        rows = connection.execute(query, {"limit": limit}).fetchall()
    finally:
        connection.close()

    candidates: list[IMessageContactCandidate] = []
    for row in rows:
        identifier = str(row["identifier"] or "").strip()
        if not identifier:
            continue
        candidates.append(
            IMessageContactCandidate(
                identifier=identifier,
                label=str(row["label"] or identifier).strip() or identifier,
                total_messages=int(row["total_messages"] or 0),
                sent_messages=int(row["sent_messages"] or 0),
                received_messages=int(row["received_messages"] or 0),
                latest_message_at=_apple_to_datetime(int(row["latest_date"] or 0)) if row["latest_date"] else None,
            )
        )
    return candidates


def _direct_chat_messages_query() -> str:
    return """
    with direct_chats as (
        select
            c.ROWID as chat_id,
            max(h.id) as identifier
        from chat c
        join chat_handle_join chj on chj.chat_id = c.ROWID
        join handle h on h.ROWID = chj.handle_id
        group by c.ROWID
        having count(distinct h.id) = 1 and max(h.id) = :contact_identifier
    )
    select distinct
        m.ROWID,
        m.guid,
        coalesce(m.text, '') as message_body,
        coalesce(m.is_from_me, 0) as is_from_me,
        coalesce(m.date, 0) as date,
        coalesce(m.associated_message_type, 0) as associated_message_type,
        m.associated_message_guid,
        coalesce(h.id, :contact_identifier, '') as sender_identifier
    from direct_chats dc
    join chat_message_join cmj on cmj.chat_id = dc.chat_id
    join message m on m.ROWID = cmj.message_id
    left join handle h on h.ROWID = m.handle_id
    order by m.date asc, m.ROWID asc
    """


def _all_messages_query() -> str:
    return """
    select
        m.ROWID,
        m.guid,
        coalesce(m.text, '') as message_body,
        coalesce(m.is_from_me, 0) as is_from_me,
        coalesce(m.date, 0) as date,
        coalesce(m.associated_message_type, 0) as associated_message_type,
        m.associated_message_guid,
        coalesce(h.id, '') as sender_identifier
    from message m
    left join handle h on h.ROWID = m.handle_id
    order by m.date asc, m.ROWID asc
    """


def _apple_to_datetime(value: int) -> datetime:
    if value > 10_000_000_000:
        return datetime.fromtimestamp((value / 1_000_000_000) + APPLE_EPOCH, tz=UTC)
    if value > 0:
        return datetime.fromtimestamp(value + APPLE_EPOCH, tz=UTC)
    return datetime.now(UTC)
