from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings
from app.models import ImportPlatform
from app.schemas.imports import ImportPreviewResponse
from app.services.imports import preview_import
from app.services.storage import StorageService


class PreviewSessionError(ValueError):
    pass


class PreviewSessionNotFoundError(PreviewSessionError):
    pass


@dataclass(slots=True)
class PreviewSession:
    id: str
    contact_id: str
    file_name: str
    file_url: str
    source_platform: ImportPlatform
    contact_identifier: str | None
    created_at: datetime


class ImportPreviewService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.storage = StorageService()
        self.preview_dir = self.settings.uploads_dir / ".preview-sessions"
        self.preview_dir.mkdir(parents=True, exist_ok=True)

    def create_preview_session(
        self,
        *,
        contact_id: str,
        upload: UploadFile,
        source_platform: ImportPlatform,
        contact_identifier: str | None = None,
    ) -> ImportPreviewResponse:
        self.cleanup_expired_sessions()
        stored = self.storage.save_upload(upload)
        try:
            with self.storage.materialize_for_processing(stored.file_url) as local_path:
                preview, _ = preview_import(
                    source_platform=source_platform,
                    file_name=upload.filename or stored.file_name,
                    file_path=str(local_path),
                    contact_identifier=contact_identifier,
                )
        except Exception:
            self.storage.delete_file(stored.file_url)
            raise

        preview_id = str(uuid4())
        session = PreviewSession(
            id=preview_id,
            contact_id=contact_id,
            file_name=upload.filename or stored.file_name,
            file_url=stored.file_url,
            source_platform=source_platform,
            contact_identifier=contact_identifier,
            created_at=datetime.now(UTC),
        )
        self._write_session(session)
        return preview.model_copy(update={"preview_id": preview_id})

    def load_session(self, preview_id: str, *, contact_id: str) -> PreviewSession:
        self.cleanup_expired_sessions()
        session_path = self._session_path(preview_id)
        if not session_path.exists():
            raise PreviewSessionNotFoundError("Import preview expired or could not be found.")

        payload = json.loads(session_path.read_text(encoding="utf-8"))
        created_at = datetime.fromisoformat(payload["created_at"])
        session = PreviewSession(
            id=payload["id"],
            contact_id=payload["contact_id"],
            file_name=payload["file_name"],
            file_url=payload["file_url"],
            source_platform=ImportPlatform(payload["source_platform"]),
            contact_identifier=payload.get("contact_identifier"),
            created_at=created_at,
        )
        if session.contact_id != contact_id:
            raise PreviewSessionNotFoundError("Import preview does not belong to this contact.")
        if self._is_expired(session.created_at):
            self.discard_session(session.id, delete_file=True)
            raise PreviewSessionNotFoundError("Import preview expired. Please preview the file again.")
        return session

    def discard_session(self, preview_id: str, *, delete_file: bool) -> None:
        session_path = self._session_path(preview_id)
        if not session_path.exists():
            return
        payload = json.loads(session_path.read_text(encoding="utf-8"))
        if delete_file:
            self.storage.delete_file(payload.get("file_url"))
        session_path.unlink(missing_ok=True)

    def cleanup_expired_sessions(self) -> None:
        for session_path in self.preview_dir.glob("*.json"):
            try:
                payload = json.loads(session_path.read_text(encoding="utf-8"))
                created_at = datetime.fromisoformat(payload["created_at"])
            except Exception:
                session_path.unlink(missing_ok=True)
                continue
            if self._is_expired(created_at):
                self.storage.delete_file(payload.get("file_url"))
                session_path.unlink(missing_ok=True)

    def _is_expired(self, created_at: datetime) -> bool:
        ttl = timedelta(hours=self.settings.import_preview_ttl_hours)
        return created_at < datetime.now(UTC) - ttl

    def _write_session(self, session: PreviewSession) -> None:
        self._session_path(session.id).write_text(
            json.dumps(
                {
                    "id": session.id,
                    "contact_id": session.contact_id,
                    "file_name": session.file_name,
                    "file_url": session.file_url,
                    "source_platform": session.source_platform.value,
                    "contact_identifier": session.contact_identifier,
                    "created_at": session.created_at.astimezone(UTC).isoformat(),
                }
            ),
            encoding="utf-8",
        )

    def _session_path(self, preview_id: str) -> Path:
        return self.preview_dir / f"{preview_id}.json"
