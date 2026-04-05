"""
iTunes / Finder iOS backup extraction.

An iPhone backup made by iTunes on Windows (or Finder on macOS) lays the
device's files out as SHA1-hashed blobs in a two-level directory tree. A
SQLite index at the backup root, ``Manifest.db``, maps
``(domain, relativePath) -> fileID`` so we can look up any logical file.

This module locates the Apple Messages database (``chat.db``) inside such a
backup and exposes a small context manager the iMessage parser can use to
treat a zipped or on-disk backup as if it were a plain ``chat.db`` upload.

Only unencrypted backups are supported. Encrypted backups store
``Manifest.db`` itself in encrypted form; decrypting it requires the user's
backup password and a keybag, which we intentionally do not collect.
"""

from __future__ import annotations

import plistlib
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

IMESSAGE_DOMAIN = "HomeDomain"
IMESSAGE_RELATIVE_PATH = "Library/SMS/sms.db"
SQLITE_HEADER = b"SQLite format 3"


class IOSBackupError(ValueError):
    """The upload is not a readable iOS backup."""


class IOSBackupEncryptedError(IOSBackupError):
    """The backup is valid but encrypted, so we cannot read Manifest.db."""


@dataclass(slots=True)
class ExtractedDatabase:
    chat_db_path: Path
    backup_root: Path
    device_name: str | None


def looks_like_ios_backup_archive(file_path: str | Path) -> bool:
    """Cheap probe: does this zip contain Manifest.db + Manifest.plist?"""
    path = Path(file_path)
    if not path.is_file() or not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return False
    has_manifest_db = any(name.endswith("Manifest.db") for name in names)
    has_manifest_plist = any(name.endswith("Manifest.plist") for name in names)
    return has_manifest_db and has_manifest_plist


def looks_like_ios_backup_folder(file_path: str | Path) -> bool:
    path = Path(file_path)
    return path.is_dir() and (path / "Manifest.db").exists()


@contextmanager
def extracted_chat_db(file_path: str | Path) -> Iterator[ExtractedDatabase]:
    """
    Yield an :class:`ExtractedDatabase` with ``chat.db`` materialized on disk.

    Works with:
    - a path to ``chat.db`` itself (yields unchanged)
    - a path to an iOS backup folder on disk
    - a path to a zipped iOS backup archive

    Temporary files are cleaned up on exit. The caller receives a live
    path and must not hold it past the ``with`` block.
    """
    path = Path(file_path)

    if path.is_file() and not zipfile.is_zipfile(path):
        yield ExtractedDatabase(chat_db_path=path, backup_root=path.parent, device_name=None)
        return

    with tempfile.TemporaryDirectory(prefix="ios-backup-") as workspace_str:
        workspace = Path(workspace_str)
        if path.is_dir():
            backup_root = _find_backup_root_on_disk(path)
            extracted = _extract_from_folder(backup_root, workspace)
        elif zipfile.is_zipfile(path):
            extracted = _extract_from_zip(path, workspace)
        else:
            raise IOSBackupError("Upload is not a chat.db file, backup folder, or backup archive.")
        yield extracted


def _extract_from_folder(backup_root: Path, workspace: Path) -> ExtractedDatabase:
    manifest = backup_root / "Manifest.db"
    if not manifest.exists():
        raise IOSBackupError("Backup is missing Manifest.db.")
    _ensure_manifest_readable(manifest)

    chat_hash = _lookup_chat_db_hash(manifest)
    if not chat_hash:
        raise IOSBackupError(
            "chat.db was not found in this backup. Make sure Messages were included before backing up."
        )
    source_blob = backup_root / chat_hash[:2] / chat_hash
    if not source_blob.exists():
        # Some older backups store blobs flat at the root.
        fallback = backup_root / chat_hash
        if not fallback.exists():
            raise IOSBackupError("Backup references chat.db but the file blob is missing on disk.")
        source_blob = fallback

    destination = workspace / "chat.db"
    shutil.copyfile(source_blob, destination)
    return ExtractedDatabase(
        chat_db_path=destination,
        backup_root=backup_root,
        device_name=_read_device_name(backup_root),
    )


def _extract_from_zip(zip_path: Path, workspace: Path) -> ExtractedDatabase:
    with zipfile.ZipFile(zip_path) as archive:
        manifest_entry = _find_entry(archive, "Manifest.db")
        if manifest_entry is None:
            raise IOSBackupError("Zip does not contain Manifest.db.")

        manifest_local = workspace / "Manifest.db"
        with archive.open(manifest_entry) as source, manifest_local.open("wb") as target:
            shutil.copyfileobj(source, target)
        _ensure_manifest_readable(manifest_local)

        chat_hash = _lookup_chat_db_hash(manifest_local)
        if not chat_hash:
            raise IOSBackupError(
                "chat.db was not found in this backup. Make sure Messages were included before backing up."
            )

        # The backup's root prefix inside the zip is whatever directory holds
        # Manifest.db. Blobs live at "<root>/<hash[:2]>/<hash>".
        root_prefix = manifest_entry.filename[: -len("Manifest.db")]
        expected = f"{root_prefix}{chat_hash[:2]}/{chat_hash}"
        blob_entry = _lookup_entry_by_name(archive, expected)
        if blob_entry is None:
            # Fall back to a basename match in case the layout is unusual.
            blob_entry = _find_entry(archive, chat_hash)
        if blob_entry is None:
            raise IOSBackupError("Backup references chat.db but the file blob is missing from the archive.")

        chat_db_path = workspace / "chat.db"
        with archive.open(blob_entry) as source, chat_db_path.open("wb") as target:
            shutil.copyfileobj(source, target)

        device_name = _read_device_name_from_zip(archive, root_prefix)

    return ExtractedDatabase(
        chat_db_path=chat_db_path,
        backup_root=workspace,
        device_name=device_name,
    )


def _find_backup_root_on_disk(folder: Path) -> Path:
    if (folder / "Manifest.db").exists():
        return folder
    # Allow one or two levels of wrapping (user zipped/copied a parent folder).
    for child in folder.iterdir():
        if child.is_dir() and (child / "Manifest.db").exists():
            return child
    for child in folder.iterdir():
        if not child.is_dir():
            continue
        for grand in child.iterdir():
            if grand.is_dir() and (grand / "Manifest.db").exists():
                return grand
    raise IOSBackupError("Could not locate Manifest.db inside the uploaded backup folder.")


def _find_entry(archive: zipfile.ZipFile, basename: str) -> zipfile.ZipInfo | None:
    """Return the first entry whose filename ends with ``/basename`` or equals it."""
    needle = f"/{basename}"
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = info.filename
        if name == basename or name.endswith(needle):
            return info
    return None


def _lookup_entry_by_name(archive: zipfile.ZipFile, full_name: str) -> zipfile.ZipInfo | None:
    try:
        return archive.getinfo(full_name)
    except KeyError:
        return None


def _ensure_manifest_readable(manifest: Path) -> None:
    with manifest.open("rb") as handle:
        header = handle.read(len(SQLITE_HEADER))
    if not header.startswith(SQLITE_HEADER):
        raise IOSBackupEncryptedError(
            "This iPhone backup is encrypted, so TextPulse cannot read the Messages database. "
            "In iTunes, uncheck 'Encrypt local backup', create a fresh backup, and try again."
        )


def _lookup_chat_db_hash(manifest_path: Path) -> str | None:
    connection = sqlite3.connect(manifest_path)
    try:
        row = connection.execute(
            "SELECT fileID FROM Files WHERE domain = ? AND relativePath = ?",
            (IMESSAGE_DOMAIN, IMESSAGE_RELATIVE_PATH),
        ).fetchone()
    finally:
        connection.close()
    if row and row[0]:
        return str(row[0])
    return None


def _read_device_name(backup_root: Path) -> str | None:
    info = backup_root / "Info.plist"
    if not info.exists():
        return None
    try:
        data = plistlib.loads(info.read_bytes())
    except Exception:
        return None
    return data.get("Device Name") or data.get("Display Name")


def _read_device_name_from_zip(archive: zipfile.ZipFile, root_prefix: str) -> str | None:
    try:
        entry = archive.getinfo(f"{root_prefix}Info.plist")
    except KeyError:
        return None
    try:
        data = plistlib.loads(archive.read(entry))
    except Exception:
        return None
    return data.get("Device Name") or data.get("Display Name")
