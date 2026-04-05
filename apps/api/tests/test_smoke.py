from __future__ import annotations

import importlib
import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient


def build_client() -> TestClient:
    db_path = Path.cwd() / "pytest-smoke.db"
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"

    from app.core.config import get_settings

    get_settings.cache_clear()

    import app.db.session as session_module
    import app.main as main_module

    importlib.reload(session_module)
    importlib.reload(main_module)

    return TestClient(main_module.app)


def test_healthcheck() -> None:
    with build_client() as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_register_and_create_contact() -> None:
    email = f"{uuid4()}@example.com"
    with build_client() as client:
        register = client.post(
            "/api/auth/register",
            json={"email": email, "password": "password123"},
        )
        assert register.status_code == 200
        token = register.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        create = client.post(
            "/api/contacts",
            json={
                "name": "Pytest Contact",
                "relationship_type": "date",
                "is_dating_mode": True,
            },
            headers=headers,
        )
        assert create.status_code == 201

        listing = client.get("/api/contacts", headers=headers)
        assert listing.status_code == 200
        assert any(contact["name"] == "Pytest Contact" for contact in listing.json())
