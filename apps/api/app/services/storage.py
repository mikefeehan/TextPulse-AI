from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import boto3
from botocore.client import Config
from fastapi import UploadFile

from app.core.config import get_settings


class UploadTooLargeError(ValueError):
    pass


@dataclass(frozen=True)
class StoredUpload:
    file_url: str
    file_size_bytes: int
    file_name: str


class StorageService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def save_upload(self, upload: UploadFile) -> StoredUpload:
        suffix = Path(upload.filename or "upload.bin").suffix
        stored_name = f"{uuid4()}{suffix}"
        upload.file.seek(0)

        if self.settings.s3_bucket:
            return self._save_to_s3(upload, stored_name)
        return self._save_to_local(upload, self.settings.uploads_dir / stored_name)

    def _save_to_local(self, upload: UploadFile, destination: Path) -> StoredUpload:
        total_bytes = 0
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with destination.open("wb") as file_handle:
                while True:
                    chunk = upload.file.read(1024 * 1024)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    self._assert_within_limit(total_bytes)
                    file_handle.write(chunk)
        except Exception:
            if destination.exists():
                destination.unlink(missing_ok=True)
            raise
        finally:
            upload.file.seek(0)

        return StoredUpload(
            file_url=str(destination.resolve()),
            file_size_bytes=total_bytes,
            file_name=upload.filename or destination.name,
        )

    def _save_to_s3(self, upload: UploadFile, stored_name: str) -> StoredUpload:
        staged_destination = self.settings.uploads_dir / f"{uuid4()}{Path(upload.filename or 'upload.bin').suffix}"

        try:
            stored = self._save_to_local(upload, staged_destination)
            client = boto3.client(
                "s3",
                region_name=self.settings.s3_region,
                endpoint_url=self.settings.s3_endpoint_url,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
                config=Config(signature_version="s3v4"),
            )
            client.upload_file(str(staged_destination), self.settings.s3_bucket, stored_name)
            return StoredUpload(
                file_url=f"s3://{self.settings.s3_bucket}/{stored_name}",
                file_size_bytes=stored.file_size_bytes,
                file_name=stored.file_name,
            )
        finally:
            staged_destination.unlink(missing_ok=True)

    @contextmanager
    def materialize_for_processing(self, file_url: str) -> Path:
        if file_url.startswith("s3://"):
            bucket, key = self._parse_s3_url(file_url)
            suffix = Path(key).suffix or ".bin"
            with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_path = Path(temp_file.name)
            client = boto3.client(
                "s3",
                region_name=self.settings.s3_region,
                endpoint_url=self.settings.s3_endpoint_url,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
                config=Config(signature_version="s3v4"),
            )
            try:
                client.download_file(bucket, key, str(temp_path))
                yield temp_path
            finally:
                temp_path.unlink(missing_ok=True)
            return

        yield Path(file_url)

    def delete_file(self, file_url: str | None) -> None:
        if not file_url:
            return
        if file_url.startswith("s3://"):
            bucket, key = self._parse_s3_url(file_url)
            client = boto3.client(
                "s3",
                region_name=self.settings.s3_region,
                endpoint_url=self.settings.s3_endpoint_url,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
                config=Config(signature_version="s3v4"),
            )
            client.delete_object(Bucket=bucket, Key=key)
            return

        Path(file_url).unlink(missing_ok=True)

    def _assert_within_limit(self, total_bytes: int) -> None:
        limit_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        if total_bytes > limit_bytes:
            raise UploadTooLargeError(
                f"Upload exceeds the {self.settings.max_upload_size_mb} MB limit."
            )

    def _parse_s3_url(self, file_url: str) -> tuple[str, str]:
        without_scheme = file_url.removeprefix("s3://")
        bucket, _, key = without_scheme.partition("/")
        return bucket, key
