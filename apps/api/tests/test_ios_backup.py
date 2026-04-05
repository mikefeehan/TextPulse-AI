"""End-to-end coverage for the iOS-backup iMessage import path.

These tests build a tiny, realistic iTunes backup on disk (Manifest.db +
hashed chat.db blob + Info.plist) and then run the two public iMessage
entry points (`discover_imessage_contacts`, `parse_imessage_db`) against
both the raw folder and a zipped copy of it. They also cover the
encrypted-backup rejection path and a backup with no Messages.
"""

from __future__ import annotations

import hashlib
import plistlib
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pytest

from app.services.parsers.imessage import discover_imessage_contacts, parse_imessage_db
from app.services.parsers.ios_backup import (
    IOSBackupEncryptedError,
    IOSBackupError,
    extracted_chat_db,
    looks_like_ios_backup_archive,
)

CHAT_DB_HASH = hashlib.sha1(b"HomeDomain-Library/SMS/sms.db").hexdigest()


def _build_chat_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
        CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, display_name TEXT, chat_identifier TEXT);
        CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
        CREATE TABLE message (
            ROWID INTEGER PRIMARY KEY, guid TEXT, text TEXT, handle_id INTEGER,
            is_from_me INTEGER, date INTEGER,
            associated_message_type INTEGER, associated_message_guid TEXT
        );
        CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
        INSERT INTO handle VALUES (1, '+15551234567');
        INSERT INTO handle VALUES (2, 'friend@icloud.com');
        INSERT INTO chat VALUES (1, '', 'iMessage;-;+15551234567');
        INSERT INTO chat VALUES (2, '', 'iMessage;-;friend@icloud.com');
        INSERT INTO chat_handle_join VALUES (1, 1);
        INSERT INTO chat_handle_join VALUES (2, 2);
        INSERT INTO message VALUES (1, 'g1', 'hey there', 1, 0, 700000000000000000, 0, NULL);
        INSERT INTO message VALUES (2, 'g2', 'yo', 1, 1, 700000001000000000, 0, NULL);
        INSERT INTO message VALUES (3, 'g3', 'how are you', 1, 0, 700000002000000000, 0, NULL);
        INSERT INTO message VALUES (4, 'g4', 'different chat', 2, 0, 700000003000000000, 0, NULL);
        INSERT INTO chat_message_join VALUES (1, 1);
        INSERT INTO chat_message_join VALUES (1, 2);
        INSERT INTO chat_message_join VALUES (1, 3);
        INSERT INTO chat_message_join VALUES (2, 4);
        """
    )
    connection.commit()
    connection.close()


def _build_backup_folder(root: Path, *, include_chat_db: bool = True) -> Path:
    """Lay out a minimal iOS backup under ``root`` and return the backup folder."""
    backup = root / "00000000-000000000000000A"
    backup.mkdir(parents=True)

    manifest = backup / "Manifest.db"
    connection = sqlite3.connect(manifest)
    connection.executescript(
        "CREATE TABLE Files (fileID TEXT, domain TEXT, relativePath TEXT, flags INT, file BLOB);"
    )
    if include_chat_db:
        connection.execute(
            "INSERT INTO Files (fileID, domain, relativePath, flags) VALUES (?, 'HomeDomain', 'Library/SMS/sms.db', 1)",
            (CHAT_DB_HASH,),
        )
    connection.commit()
    connection.close()

    (backup / "Manifest.plist").write_bytes(plistlib.dumps({"Version": "10.0"}))
    (backup / "Info.plist").write_bytes(plistlib.dumps({"Device Name": "Test iPhone"}))

    if include_chat_db:
        blob_dir = backup / CHAT_DB_HASH[:2]
        blob_dir.mkdir()
        chat_db_tmp = root / "chat.db"
        _build_chat_db(chat_db_tmp)
        shutil.copyfile(chat_db_tmp, blob_dir / CHAT_DB_HASH)
        chat_db_tmp.unlink()

    return backup


def _zip_backup(backup_folder: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in backup_folder.rglob("*"):
            if file.is_file():
                archive.write(file, arcname=file.relative_to(backup_folder.parent))
    return destination


def test_discover_and_parse_from_backup_folder(tmp_path: Path) -> None:
    backup = _build_backup_folder(tmp_path)

    candidates = discover_imessage_contacts(str(backup))
    identifiers = {candidate.identifier for candidate in candidates}
    assert identifiers == {"+15551234567", "friend@icloud.com"}

    phone_candidate = next(c for c in candidates if c.identifier == "+15551234567")
    assert phone_candidate.total_messages == 3
    assert phone_candidate.sent_messages == 1
    assert phone_candidate.received_messages == 2

    messages = parse_imessage_db(str(backup), "+15551234567")
    assert [(m.sender.value, m.text) for m in messages] == [
        ("contact", "hey there"),
        ("user", "yo"),
        ("contact", "how are you"),
    ]


def test_discover_and_parse_from_backup_zip(tmp_path: Path) -> None:
    backup = _build_backup_folder(tmp_path)
    archive_path = _zip_backup(backup, tmp_path / "backup.zip")

    assert looks_like_ios_backup_archive(archive_path)

    candidates = discover_imessage_contacts(str(archive_path))
    assert any(c.identifier == "+15551234567" for c in candidates)

    messages = parse_imessage_db(str(archive_path), "+15551234567")
    assert len(messages) == 3
    assert messages[0].text == "hey there"


def test_encrypted_backup_rejected(tmp_path: Path) -> None:
    backup = tmp_path / "encrypted-backup"
    backup.mkdir()
    # A real encrypted Manifest.db does not start with the SQLite magic.
    (backup / "Manifest.db").write_bytes(b"\x00\x01\x02\x03not-sqlite-bytes")
    (backup / "Manifest.plist").write_bytes(plistlib.dumps({"Version": "10.0"}))

    with pytest.raises(IOSBackupEncryptedError):
        with extracted_chat_db(str(backup)):
            pass


def test_backup_without_chat_db_raises(tmp_path: Path) -> None:
    backup = _build_backup_folder(tmp_path, include_chat_db=False)
    with pytest.raises(IOSBackupError):
        with extracted_chat_db(str(backup)):
            pass
