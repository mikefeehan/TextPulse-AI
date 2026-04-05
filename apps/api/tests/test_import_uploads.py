from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from uuid import uuid4

from tests.test_smoke import build_client


def _auth_headers(client):
    email = f"{uuid4()}@example.com"
    register = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert register.status_code == 200
    token = register.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_contact(client, headers):
    create = client.post(
        "/api/contacts",
        json={
            "name": "Upload Test Contact",
            "relationship_type": "date",
            "is_dating_mode": True,
        },
        headers=headers,
    )
    assert create.status_code == 201
    return create.json()["id"]


def _build_imessage_db(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            create table handle (
                ROWID integer primary key,
                id text
            );
            create table message (
                ROWID integer primary key,
                guid text,
                text text,
                handle_id integer,
                date integer,
                is_from_me integer,
                associated_message_type integer default 0,
                associated_message_guid text
            );
            create table chat (
                ROWID integer primary key,
                chat_identifier text,
                display_name text
            );
            create table chat_handle_join (
                chat_id integer,
                handle_id integer
            );
            create table chat_message_join (
                chat_id integer,
                message_id integer
            );
            """
        )
        connection.executemany(
            "insert into handle (ROWID, id) values (?, ?)",
            [
                (1, "+15550001111"),
                (2, "+15550002222"),
            ],
        )
        connection.executemany(
            "insert into chat (ROWID, chat_identifier, display_name) values (?, ?, ?)",
            [
                (1, "+15550001111", None),
                (2, "+15550002222", None),
            ],
        )
        connection.executemany(
            "insert into chat_handle_join (chat_id, handle_id) values (?, ?)",
            [
                (1, 1),
                (2, 2),
            ],
        )
        connection.executemany(
            """
            insert into message (ROWID, guid, text, handle_id, date, is_from_me, associated_message_type, associated_message_guid)
            values (?, ?, ?, ?, ?, ?, 0, null)
            """,
            [
                (1, "guid-1", "hey from alex", 1, 10_000_000_000, 0),
                (2, "guid-2", "reply to alex", None, 11_000_000_000, 1),
                (3, "guid-3", "hey from sam", 2, 12_000_000_000, 0),
                (4, "guid-4", "reply to sam", None, 13_000_000_000, 1),
            ],
        )
        connection.executemany(
            "insert into chat_message_join (chat_id, message_id) values (?, ?)",
            [
                (1, 1),
                (1, 2),
                (2, 3),
                (2, 4),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def test_large_whatsapp_upload_flow() -> None:
    with build_client() as client:
        headers = _auth_headers(client)
        contact_id = _create_contact(client, headers)

        transcript = "\n".join(
            f"[03/{(index % 28) + 1:02d}/26, 19:{index % 60:02d}:00] "
            f"{'Alex' if index % 2 else 'Me'}: message number {index} about plans and timing"
            for index in range(2500)
        )

        upload = client.post(
            f"/api/contacts/{contact_id}/imports/upload",
            headers=headers,
            data={
                "source_platform": "whatsapp",
                "contact_identifier": "Alex",
                "run_analysis": "true",
            },
            files={"file": ("history.txt", transcript.encode("utf-8"), "text/plain")},
        )

        assert upload.status_code == 202, upload.text
        body = upload.json()
        import_id = body["import_id"]
        assert body["queued"] is True

        status_response = client.get(
            f"/api/contacts/{contact_id}/imports/{import_id}",
            headers=headers,
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] in {"processing", "completed"}

        detail = client.get(f"/api/contacts/{contact_id}", headers=headers)
        assert detail.status_code == 200
        imports = detail.json()["imports"]
        assert imports[0]["file_name"] == "history.txt"
        assert imports[0]["status"] == "completed"
        assert imports[0]["message_count"] >= 2400


def test_preview_confirm_flow() -> None:
    with build_client() as client:
        headers = _auth_headers(client)
        contact_id = _create_contact(client, headers)
        transcript = "\n".join(
            [
                "[03/18/26, 09:00:00] Alex: Morning check-in",
                "[03/18/26, 09:02:00] Me: Morning, how did the meeting go?",
                "[03/18/26, 09:05:00] Alex: Better than expected",
            ]
        )

        preview = client.post(
            f"/api/contacts/{contact_id}/imports/preview",
            headers=headers,
            data={
                "source_platform": "whatsapp",
                "contact_identifier": "Alex",
            },
            files={"file": ("history.txt", transcript.encode("utf-8"), "text/plain")},
        )

        assert preview.status_code == 200, preview.text
        preview_body = preview.json()
        assert preview_body["preview_id"]
        assert preview_body["message_count"] == 3

        confirm = client.post(
            f"/api/contacts/{contact_id}/imports/confirm",
            headers=headers,
            json={"preview_id": preview_body["preview_id"], "run_analysis": True},
        )

        assert confirm.status_code == 202, confirm.text
        assert confirm.json()["queued"] is True
        import_id = confirm.json()["import_id"]

        status_response = client.get(
            f"/api/contacts/{contact_id}/imports/{import_id}",
            headers=headers,
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "completed"


def test_imessage_preview_guides_contact_selection(tmp_path: Path) -> None:
    db_path = tmp_path / "chat.db"
    _build_imessage_db(db_path)

    with build_client() as client:
        headers = _auth_headers(client)
        contact_id = _create_contact(client, headers)

        preview = client.post(
            f"/api/contacts/{contact_id}/imports/preview",
            headers=headers,
            data={"source_platform": "imessage"},
            files={"file": ("chat.db", db_path.read_bytes(), "application/octet-stream")},
        )

        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["selection_required"] is True
        assert body["message_count"] == 0
        assert body["contact_options"][0]["identifier"] == "+15550001111"

        rejected = client.post(
            f"/api/contacts/{contact_id}/imports/confirm",
            headers=headers,
            json={"preview_id": body["preview_id"], "run_analysis": False},
        )
        assert rejected.status_code == 400

        confirmed = client.post(
            f"/api/contacts/{contact_id}/imports/confirm",
            headers=headers,
            json={
                "preview_id": body["preview_id"],
                "run_analysis": False,
                "contact_identifier": "+15550001111",
            },
        )
        assert confirmed.status_code == 202, confirmed.text
        import_id = confirmed.json()["import_id"]

        status_response = client.get(
            f"/api/contacts/{contact_id}/imports/{import_id}",
            headers=headers,
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "completed"
        assert status_response.json()["message_count"] == 2


def test_failed_import_rolls_back_partial_messages_and_can_retry(monkeypatch) -> None:
    with build_client() as client:
        headers = _auth_headers(client)
        contact_id = _create_contact(client, headers)
        transcript = "\n".join(
            f"[03/19/26, 18:{index % 60:02d}:00] {'Alex' if index % 2 else 'Me'}: retry case {index}"
            for index in range(40)
        )

        def blow_up(*args, **kwargs):
            raise RuntimeError("analysis exploded")

        monkeypatch.setattr("app.services.imports.generate_contact_profile", blow_up)

        upload = client.post(
            f"/api/contacts/{contact_id}/imports/upload",
            headers=headers,
            data={
                "source_platform": "whatsapp",
                "contact_identifier": "Alex",
                "run_analysis": "true",
            },
            files={"file": ("retry.txt", transcript.encode("utf-8"), "text/plain")},
        )

        assert upload.status_code == 202, upload.text
        import_id = upload.json()["import_id"]

        status_response = client.get(
            f"/api/contacts/{contact_id}/imports/{import_id}",
            headers=headers,
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "failed"

        from app.db.session import SessionLocal
        from app.models import Message

        with SessionLocal() as db:
            assert db.query(Message).filter(Message.contact_id == contact_id).count() == 0

        monkeypatch.undo()

        retry = client.post(
            f"/api/contacts/{contact_id}/imports/{import_id}/retry",
            headers=headers,
        )
        assert retry.status_code == 202, retry.text
        assert retry.json()["status"] == "processing"

        completed = client.get(
            f"/api/contacts/{contact_id}/imports/{import_id}",
            headers=headers,
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"

        from app.db.session import SessionLocal
        from app.models import Message

        with SessionLocal() as db:
            assert db.query(Message).filter(Message.contact_id == contact_id).count() > 0


def test_upload_respects_max_size_limit() -> None:
    os.environ["MAX_UPLOAD_SIZE_MB"] = "1"
    try:
        with build_client() as client:
            headers = _auth_headers(client)
            contact_id = _create_contact(client, headers)
            oversized = ("x" * (2 * 1024 * 1024)).encode("utf-8")

            upload = client.post(
                f"/api/contacts/{contact_id}/imports/upload",
                headers=headers,
                data={"source_platform": "csv", "run_analysis": "false"},
                files={"file": ("too-big.txt", oversized, "text/plain")},
            )

            assert upload.status_code == 413
    finally:
        os.environ.pop("MAX_UPLOAD_SIZE_MB", None)
