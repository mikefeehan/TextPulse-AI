from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings


@dataclass(slots=True)
class ImportJobOptions:
    contact_identifier: str | None
    run_analysis: bool


class ImportJobOptionsStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.directory = self.settings.uploads_dir / ".import-jobs"
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        import_id: str,
        *,
        contact_identifier: str | None,
        run_analysis: bool,
    ) -> None:
        self._path(import_id).write_text(
            json.dumps(
                {
                    "contact_identifier": contact_identifier,
                    "run_analysis": run_analysis,
                }
            ),
            encoding="utf-8",
        )

    def load(self, import_id: str) -> ImportJobOptions:
        path = self._path(import_id)
        if not path.exists():
            return ImportJobOptions(contact_identifier=None, run_analysis=True)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ImportJobOptions(
            contact_identifier=payload.get("contact_identifier"),
            run_analysis=bool(payload.get("run_analysis", True)),
        )

    def _path(self, import_id: str) -> Path:
        return self.directory / f"{import_id}.json"
