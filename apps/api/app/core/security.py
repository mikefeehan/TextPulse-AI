from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.types import JSON, Text, TypeDecorator

from app.core.config import get_settings


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 310_000
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    encoded = base64.urlsafe_b64encode(digest).decode("utf-8")
    return f"pbkdf2_sha256${iterations}${salt}${encoded}"


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        _, iterations_text, salt, expected = hashed_password.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations_text),
        )
        actual = base64.urlsafe_b64encode(digest).decode("utf-8")
        return hmac.compare_digest(actual, expected)
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expires_at}
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )


@dataclass
class EncryptionManager:
    key: bytes

    @classmethod
    def from_settings(cls) -> "EncryptionManager":
        key = base64.urlsafe_b64decode(get_settings().encryption_key.encode("utf-8"))
        return cls(key=key)

    def encrypt(self, plaintext: str) -> str:
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(self.key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")

    def decrypt(self, token: str | None) -> str | None:
        if token is None:
            return None
        payload = base64.urlsafe_b64decode(token.encode("utf-8"))
        nonce = payload[:12]
        ciphertext = payload[12:]
        aesgcm = AESGCM(self.key)
        return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


class EncryptedString(TypeDecorator[str]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return EncryptionManager.from_settings().encrypt(value)

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        return EncryptionManager.from_settings().decrypt(value)


class EncryptedJSON(TypeDecorator[dict[str, Any] | list[Any]]):
    impl = Text
    cache_ok = True

    def process_bind_param(
        self,
        value: dict[str, Any] | list[Any] | None,
        dialect: Any,
    ) -> str | None:
        if value is None:
            return None
        return EncryptionManager.from_settings().encrypt(
            json.dumps(value, default=_json_default)
        )

    def process_result_value(
        self,
        value: str | None,
        dialect: Any,
    ) -> dict[str, Any] | list[Any] | None:
        decrypted = EncryptionManager.from_settings().decrypt(value)
        return json.loads(decrypted) if decrypted is not None else None


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class FlexibleEmbedding(TypeDecorator[list[float] | None]):
    impl = JSON
    cache_ok = True

    def process_bind_param(
        self,
        value: list[float] | None,
        dialect: Any,
    ) -> list[float] | None:
        return value

    def process_result_value(
        self,
        value: list[float] | None,
        dialect: Any,
    ) -> list[float] | None:
        return value
