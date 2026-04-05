from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Contact, ImportPlatform, ImportRecord, ImportStatus, Message, MessageType, SenderType, VaultCategory
from app.schemas.imports import ImportPreviewResponse, ImportStatusResponse, ParsedMessagePreview
from app.seed.default_categories import DEFAULT_VAULT_CATEGORIES
from app.services.analysis_engine import generate_contact_profile
from app.services.import_jobs import ImportJobOptionsStore
from app.services.parsers.imessage import discover_imessage_contacts
from app.services.parsers import parse_messages
from app.services.storage import StorageService
from app.services.text_utils import deterministic_embedding, sentiment_score


def ensure_default_categories(db: Session, contact: Contact) -> None:
    existing = db.scalars(
        select(VaultCategory).where(VaultCategory.contact_id == contact.id)
    ).all()
    if existing:
        return
    for index, payload in enumerate(DEFAULT_VAULT_CATEGORIES):
        db.add(
            VaultCategory(
                contact_id=contact.id,
                name=payload["name"],
                emoji=payload["emoji"],
                description=payload["description"],
                is_default=True,
                sort_order=index,
            )
        )
    db.flush()


def preview_import(
    source_platform: ImportPlatform,
    file_name: str,
    content: str | None = None,
    file_path: str | None = None,
    contact_identifier: str | None = None,
) -> tuple[ImportPreviewResponse, list]:
    if source_platform == ImportPlatform.IMESSAGE and file_path and not contact_identifier:
        contact_candidates = discover_imessage_contacts(file_path)
        return (
            ImportPreviewResponse(
                file_name=file_name,
                source_platform=source_platform,
                message_count=0,
                date_range={"start": None, "end": None},
                previews=[],
                stats={
                    "direct_chats_found": len(contact_candidates),
                    "recommended_path": "Choose the person first, then confirm the import.",
                },
                selection_required=True,
                contact_options=[
                    {
                        "identifier": candidate.identifier,
                        "label": candidate.label,
                        "total_messages": candidate.total_messages,
                        "sent_messages": candidate.sent_messages,
                        "received_messages": candidate.received_messages,
                        "latest_message_at": candidate.latest_message_at,
                    }
                    for candidate in contact_candidates
                ],
            ),
            [],
        )

    parsed = parse_messages(
        source_platform=source_platform,
        file_path=file_path,
        content=content,
        contact_identifier=contact_identifier,
    )
    return build_preview(source_platform=source_platform, file_name=file_name, parsed=parsed), parsed


def build_preview(
    *,
    source_platform: ImportPlatform,
    file_name: str,
    parsed: list,
) -> ImportPreviewResponse:
    parsed.sort(key=lambda row: row.timestamp)
    previews = [
        ParsedMessagePreview(
            canonical_id=item.canonical_id,
            sender=item.sender.value,
            text=item.text,
            timestamp=item.timestamp,
            message_type=item.message_type.value,
        )
        for item in parsed[:12]
    ]
    date_range = {
        "start": parsed[0].timestamp if parsed else None,
        "end": parsed[-1].timestamp if parsed else None,
    }
    sender_counts: dict[str, int] = defaultdict(int)
    for item in parsed:
        sender_counts[item.sender.value] += 1

    return ImportPreviewResponse(
        file_name=file_name,
        source_platform=source_platform,
        message_count=len(parsed),
        date_range=date_range,
        previews=previews,
        stats={
            "user_messages": sender_counts.get(SenderType.USER.value, 0),
            "contact_messages": sender_counts.get(SenderType.CONTACT.value, 0),
            "text_messages": sum(1 for item in parsed if item.message_type == MessageType.TEXT),
            "reaction_messages": sum(1 for item in parsed if item.message_type == MessageType.REACTION),
        },
        selection_required=False,
        contact_options=[],
    )


def serialize_import_record(import_record: ImportRecord) -> ImportStatusResponse:
    return ImportStatusResponse(
        id=import_record.id,
        file_name=import_record.file_name,
        source_platform=import_record.source_platform.value,
        message_count=import_record.message_count,
        status=import_record.status.value,
        imported_at=import_record.imported_at,
        date_range={
            "start": import_record.date_range_start,
            "end": import_record.date_range_end,
        },
        error_details=import_record.error_details,
    )


def create_import_record(
    db: Session,
    *,
    contact: Contact,
    source_platform: ImportPlatform,
    file_name: str,
    file_url: str | None,
) -> ImportRecord:
    import_record = ImportRecord(
        contact_id=contact.id,
        source_platform=source_platform,
        file_name=file_name,
        file_url=file_url,
        message_count=0,
        date_range_start=None,
        date_range_end=None,
        status=ImportStatus.PROCESSING,
        error_details=None,
    )
    db.add(import_record)
    db.flush()
    return import_record


def create_upload_import(
    db: Session,
    contact: Contact,
    upload: UploadFile,
    source_platform: ImportPlatform,
) -> ImportRecord:
    storage = StorageService()
    stored_upload = storage.save_upload(upload)
    return create_import_record(
        db,
        contact=contact,
        source_platform=source_platform,
        file_name=upload.filename or stored_upload.file_name,
        file_url=stored_upload.file_url,
    )


def create_staged_import(
    db: Session,
    *,
    contact: Contact,
    source_platform: ImportPlatform,
    file_name: str,
    file_url: str,
) -> ImportRecord:
    return create_import_record(
        db,
        contact=contact,
        source_platform=source_platform,
        file_name=file_name,
        file_url=file_url,
    )


def retry_import_record(
    db: Session,
    *,
    import_record: ImportRecord,
) -> ImportRecord:
    _delete_messages_for_import(db, import_record.id)
    import_record.status = ImportStatus.PROCESSING
    import_record.error_details = None
    import_record.message_count = 0
    import_record.date_range_start = None
    import_record.date_range_end = None
    db.flush()
    return import_record


def process_import_record_job(
    import_id: str,
    *,
    contact_identifier: str | None = None,
    run_analysis: bool = True,
    raise_on_failure: bool = False,
) -> str:
    db = SessionLocal()
    try:
        stored_options = ImportJobOptionsStore().load(import_id)
        effective_contact_identifier = contact_identifier if contact_identifier is not None else stored_options.contact_identifier
        effective_run_analysis = run_analysis if run_analysis is not None else stored_options.run_analysis
        import_record = db.get(ImportRecord, import_id)
        if import_record is None:
            return "missing-import"
        contact = db.get(Contact, import_record.contact_id)
        if contact is None:
            import_record.status = ImportStatus.FAILED
            import_record.error_details = "Contact for this import no longer exists."
            db.commit()
            return "missing-contact"
        try:
            with db.begin_nested():
                _process_import_record(
                    db,
                    contact,
                    import_record,
                    contact_identifier=effective_contact_identifier,
                    run_analysis=effective_run_analysis,
                )
            db.commit()
            return "ok"
        except Exception as error:
            db.rollback()
            failed_import = db.get(ImportRecord, import_id)
            failed_contact = db.get(Contact, import_record.contact_id)
            if failed_import is not None:
                failed_import.status = ImportStatus.FAILED
                failed_import.error_details = str(error)[:2000]
            if failed_contact is not None:
                failed_contact.updated_at = datetime.now(UTC)
            db.commit()
            if raise_on_failure:
                raise
            return "failed"
    finally:
        db.close()


def ingest_paste(
    db: Session,
    contact: Contact,
    file_name: str,
    content: str,
    source_platform: ImportPlatform = ImportPlatform.PASTE,
    contact_identifier: str | None = None,
    run_analysis: bool = True,
) -> dict[str, Any]:
    preview, parsed = preview_import(
        source_platform=source_platform,
        file_name=file_name,
        content=content,
        contact_identifier=contact_identifier,
    )
    import_record = create_import_record(
        db,
        contact=contact,
        source_platform=source_platform,
        file_name=file_name,
        file_url=None,
    )
    import_record.date_range_start = preview.date_range.start
    import_record.date_range_end = preview.date_range.end

    try:
        with db.begin_nested():
            inserted_count = _persist_messages(db, contact, import_record, parsed)
            ensure_default_categories(db, contact)
            import_record.message_count = inserted_count
            import_record.status = ImportStatus.COMPLETED
            import_record.error_details = None
            contact.updated_at = datetime.now(UTC)
            if run_analysis:
                generate_contact_profile(db, contact)
        db.commit()
        db.refresh(import_record)
    except Exception as error:
        db.rollback()
        failed_import = db.get(ImportRecord, import_record.id)
        if failed_import is not None:
            failed_import.status = ImportStatus.FAILED
            failed_import.error_details = str(error)[:2000]
        failed_contact = db.get(Contact, contact.id)
        if failed_contact is not None:
            failed_contact.updated_at = datetime.now(UTC)
        db.commit()
        raise

    return {
        "import_id": import_record.id,
        "status": import_record.status.value,
        "message_count": import_record.message_count,
        "profile_refreshed": run_analysis,
        "queued": False,
        "preview": preview,
        "import_record": serialize_import_record(import_record),
    }


def _process_import_record(
    db: Session,
    contact: Contact,
    import_record: ImportRecord,
    *,
    contact_identifier: str | None = None,
    run_analysis: bool = True,
) -> None:
    storage = StorageService()
    with storage.materialize_for_processing(import_record.file_url or "") as local_path:
        parsed = parse_messages(
            source_platform=import_record.source_platform,
            file_path=str(local_path),
            contact_identifier=contact_identifier,
        )
    preview = build_preview(
        source_platform=import_record.source_platform,
        file_name=import_record.file_name,
        parsed=parsed,
    )
    inserted_count = _persist_messages(db, contact, import_record, parsed)
    ensure_default_categories(db, contact)
    import_record.message_count = inserted_count
    import_record.date_range_start = preview.date_range.start
    import_record.date_range_end = preview.date_range.end
    import_record.status = ImportStatus.COMPLETED
    import_record.error_details = None
    contact.updated_at = datetime.now(UTC)
    db.flush()

    if run_analysis:
        generate_contact_profile(db, contact)
        db.flush()


def _delete_messages_for_import(db: Session, import_id: str) -> None:
    messages = db.scalars(select(Message).where(Message.import_id == import_id)).all()
    for message in messages:
        db.delete(message)
    db.flush()


def _persist_messages(db: Session, contact: Contact, import_record: ImportRecord, parsed: list) -> int:
    parsed.sort(key=lambda row: row.timestamp)
    existing_ids = {
        row[0]
        for row in db.execute(
            select(Message.canonical_id).where(Message.contact_id == contact.id)
        ).all()
    }
    last_seen_by_sender: dict[SenderType, datetime] = {}
    session_id = 0
    previous_timestamp: datetime | None = None
    inserted_count = 0

    for parsed_message in parsed:
        if parsed_message.canonical_id in existing_ids:
            continue
        if previous_timestamp is None or (parsed_message.timestamp - previous_timestamp).total_seconds() > 14_400:
            session_id += 1
        other_sender = SenderType.USER if parsed_message.sender == SenderType.CONTACT else SenderType.CONTACT
        response_time = None
        if other_sender in last_seen_by_sender:
            response_time = max(
                0.0,
                (parsed_message.timestamp - last_seen_by_sender[other_sender]).total_seconds(),
            )

        db.add(
            Message(
                contact_id=contact.id,
                import_id=import_record.id,
                canonical_id=parsed_message.canonical_id,
                sender=parsed_message.sender,
                message_text=parsed_message.text,
                timestamp=parsed_message.timestamp if parsed_message.timestamp.tzinfo else parsed_message.timestamp.replace(tzinfo=UTC),
                message_type=parsed_message.message_type,
                response_time_seconds=response_time,
                sentiment_score=sentiment_score(parsed_message.text),
                session_id=session_id,
                metadata_json=parsed_message.metadata_json,
                embedding=deterministic_embedding(parsed_message.text),
            )
        )
        inserted_count += 1
        existing_ids.add(parsed_message.canonical_id)
        last_seen_by_sender[parsed_message.sender] = parsed_message.timestamp
        previous_timestamp = parsed_message.timestamp

    return inserted_count
