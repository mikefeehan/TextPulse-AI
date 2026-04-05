from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.contacts import _get_contact_or_404
from app.core.config import get_settings
from app.db.session import get_db
from app.models import ImportPlatform, ImportRecord, ImportStatus, User
from app.schemas.imports import ConfirmImportRequest, ImportInstruction, ImportPreviewResponse, ImportStatusResponse, ImportUploadResponse, PasteImportRequest
from app.services.import_jobs import ImportJobOptionsStore
from app.services.import_previews import ImportPreviewService, PreviewSessionNotFoundError
from app.services.imports import create_staged_import, create_upload_import, ingest_paste, process_import_record_job, retry_import_record, serialize_import_record
from app.services.parsers.ios_backup import IOSBackupError
from app.services.storage import UploadTooLargeError
from app.workers.tasks import process_import_record_task

router = APIRouter()
settings = get_settings()

INSTRUCTIONS = {
    "imessage": ImportInstruction(
        platform="imessage",
        title="Import Apple Messages from an iPhone backup",
        steps=[
            "On Windows, plug the iPhone into this computer and let iTunes make a local backup. Make sure 'Encrypt local backup' is unchecked.",
            "Open `%APPDATA%\\Apple\\MobileSync\\Backup` and zip the backup folder named after your device.",
            "Drop the backup zip into the upload box below. TextPulse finds chat.db inside automatically.",
            "On Mac you can skip the backup: quit Messages and drop `~/Library/Messages/chat.db` here directly.",
        ],
        notes=[
            "Encrypted backups are not supported yet because decrypting Manifest.db requires your backup password. Uncheck encryption, re-back up, and try again.",
            "After scanning, TextPulse surfaces one-to-one threads in the backup so you can pick the person without hunting for a phone number.",
        ],
        accepted_extensions=[".zip", ".db", ".sqlite", ".sqlite3"],
    ),
    "whatsapp": ImportInstruction(
        platform="whatsapp",
        title="Export chat from WhatsApp",
        steps=[
            "Open the chat, tap More, then choose Export Chat.",
            "Send the export to yourself without media for faster processing.",
            "Upload the exported .txt file here.",
        ],
        notes=["We support both standard WhatsApp export formats."],
        accepted_extensions=[".txt", ".zip"],
    ),
    "telegram": ImportInstruction(
        platform="telegram",
        title="Export Telegram JSON",
        steps=[
            "Use Telegram Desktop and export the target chat as JSON.",
            "Include message text and timestamps in the export.",
            "Upload the JSON file to build or refresh the dossier.",
        ],
        notes=["Telegram exports can be large, so JSON is preferred over HTML."],
        accepted_extensions=[".json"],
    ),
    "instagram": ImportInstruction(
        platform="instagram",
        title="Upload Instagram DM export",
        steps=[
            "Request your Instagram data download in JSON format.",
            "Open the messages/inbox folder and find the thread file.",
            "Upload the JSON file for the conversation you want to analyze.",
        ],
        notes=["Thread-level JSON files give the cleanest parsing result."],
        accepted_extensions=[".json"],
    ),
    "android_sms": ImportInstruction(
        platform="android_sms",
        title="Upload SMS Backup & Restore XML",
        steps=[
            "Export your text history from SMS Backup & Restore.",
            "Choose the XML export format.",
            "Upload the XML file directly in the import hub.",
        ],
        notes=["This parser handles large SMS archives well."],
        accepted_extensions=[".xml"],
    ),
    "csv": ImportInstruction(
        platform="csv",
        title="Upload generic CSV or transcript text",
        steps=[
            "Prepare a file with timestamp, sender, and message body fields.",
            "Upload the CSV, TXT, or transcript export.",
            "Use paste import if copying the transcript is faster than exporting it.",
        ],
        notes=["Common CSV column names are auto-detected."],
        accepted_extensions=[".csv", ".txt"],
    ),
    "screenshot": ImportInstruction(
        platform="screenshot",
        title="Upload screenshots",
        steps=[
            "Drop one or more screenshots from the conversation.",
            "Let OCR extract the transcript into a structured timeline.",
            "Review the preview before committing the import.",
        ],
        notes=["OCR quality improves with tighter crops and visible timestamps."],
        accepted_extensions=[".png", ".jpg", ".jpeg"],
    ),
    "paste": ImportInstruction(
        platform="paste",
        title="Paste transcript blocks",
        steps=[
            "Copy the raw conversation text from any source.",
            "Paste it into the quick import field.",
            "Run the import to append that context into the dossier.",
        ],
        notes=["Best for fast coaching or incremental updates."],
        accepted_extensions=[".txt"],
    ),
}


def _queue_import_processing(
    *,
    background_tasks: BackgroundTasks,
    import_record: ImportRecord,
    contact_identifier: str | None,
    run_analysis: bool,
) -> None:
    ImportJobOptionsStore().save(
        import_record.id,
        contact_identifier=contact_identifier,
        run_analysis=run_analysis,
    )
    if settings.imports_use_celery:
        process_import_record_task.delay(
            import_record.id,
            contact_identifier=contact_identifier,
            run_analysis=run_analysis,
        )
        return

    background_tasks.add_task(
        process_import_record_job,
        import_record.id,
        contact_identifier=contact_identifier,
        run_analysis=run_analysis,
    )


@router.get("/import-instructions", response_model=list[ImportInstruction])
def get_import_instructions() -> list[ImportInstruction]:
    return list(INSTRUCTIONS.values())


@router.post(
    "/{contact_id}/imports/upload",
    response_model=ImportUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_import(
    contact_id: str,
    background_tasks: BackgroundTasks,
    source_platform: ImportPlatform = Form(...),
    contact_identifier: str | None = Form(default=None),
    run_analysis: bool = Form(default=True),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportUploadResponse:
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required.")
    try:
        import_record = create_upload_import(
            db=db,
            contact=contact,
            upload=file,
            source_platform=source_platform,
        )
        db.commit()
        db.refresh(import_record)
    except UploadTooLargeError as error:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(error)) from error

    _queue_import_processing(
        background_tasks=background_tasks,
        import_record=import_record,
        contact_identifier=contact_identifier,
        run_analysis=run_analysis,
    )

    return ImportUploadResponse(
        import_id=import_record.id,
        status=import_record.status.value,
        message_count=import_record.message_count,
        profile_refreshed=False,
        queued=True,
        preview=None,
        import_record=serialize_import_record(import_record),
    )


@router.post("/{contact_id}/imports/paste", response_model=ImportUploadResponse)
def paste_import(
    contact_id: str,
    payload: PasteImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportUploadResponse:
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    response = ingest_paste(
        db=db,
        contact=contact,
        file_name=payload.file_name,
        content=payload.content,
        source_platform=payload.source_platform,
        contact_identifier=payload.contact_identifier,
        run_analysis=payload.run_analysis,
    )
    return ImportUploadResponse.model_validate(response)


@router.get("/{contact_id}/imports", response_model=list[ImportStatusResponse])
def list_contact_imports(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ImportStatusResponse]:
    _get_contact_or_404(db, current_user.id, contact_id)
    imports = db.query(ImportRecord).filter(ImportRecord.contact_id == contact_id).order_by(ImportRecord.imported_at.desc()).all()
    return [serialize_import_record(item) for item in imports]


@router.get("/{contact_id}/imports/{import_id}", response_model=ImportStatusResponse)
def get_import_status(
    contact_id: str,
    import_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportStatusResponse:
    _get_contact_or_404(db, current_user.id, contact_id)
    import_record = db.get(ImportRecord, import_id)
    if import_record is None or import_record.contact_id != contact_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found.")
    return serialize_import_record(import_record)


@router.post("/{contact_id}/imports/preview", response_model=ImportPreviewResponse)
async def preview_import_route(
    contact_id: str,
    source_platform: ImportPlatform = Form(...),
    contact_identifier: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportPreviewResponse:
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    preview_service = ImportPreviewService()
    try:
        return preview_service.create_preview_session(
            contact_id=contact.id,
            upload=file,
            source_platform=source_platform,
            contact_identifier=contact_identifier,
        )
    except UploadTooLargeError as error:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(error)) from error
    except IOSBackupError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post(
    "/{contact_id}/imports/confirm",
    response_model=ImportUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def confirm_import(
    contact_id: str,
    payload: ConfirmImportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportUploadResponse:
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    preview_service = ImportPreviewService()
    try:
        preview_session = preview_service.load_session(payload.preview_id, contact_id=contact.id)
    except PreviewSessionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    effective_contact_identifier = payload.contact_identifier or preview_session.contact_identifier
    if preview_session.source_platform == ImportPlatform.IMESSAGE and not effective_contact_identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose the person from the iPhone message database before confirming the import.",
        )

    import_record = create_staged_import(
        db,
        contact=contact,
        source_platform=preview_session.source_platform,
        file_name=preview_session.file_name,
        file_url=preview_session.file_url,
    )
    db.commit()
    db.refresh(import_record)
    preview_service.discard_session(payload.preview_id, delete_file=False)

    _queue_import_processing(
        background_tasks=background_tasks,
        import_record=import_record,
        contact_identifier=effective_contact_identifier,
        run_analysis=payload.run_analysis,
    )

    return ImportUploadResponse(
        import_id=import_record.id,
        status=import_record.status.value,
        message_count=import_record.message_count,
        profile_refreshed=False,
        queued=True,
        preview=None,
        import_record=serialize_import_record(import_record),
    )


@router.post(
    "/{contact_id}/imports/{import_id}/retry",
    response_model=ImportStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_import(
    contact_id: str,
    import_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportStatusResponse:
    _get_contact_or_404(db, current_user.id, contact_id)
    import_record = db.get(ImportRecord, import_id)
    if import_record is None or import_record.contact_id != contact_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found.")
    if import_record.status != ImportStatus.FAILED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed imports can be retried.")
    if not import_record.file_url:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This import cannot be retried automatically.")

    options = ImportJobOptionsStore().load(import_id)
    retry_import_record(db, import_record=import_record)
    db.commit()
    db.refresh(import_record)

    _queue_import_processing(
        background_tasks=background_tasks,
        import_record=import_record,
        contact_identifier=options.contact_identifier,
        run_analysis=options.run_analysis,
    )
    return serialize_import_record(import_record)
