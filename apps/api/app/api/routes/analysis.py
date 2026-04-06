from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.contacts import _get_contact_or_404
from app.db.session import get_db
from app.models import User
from app.schemas.contacts import AnalysisRegenerateRequest
from app.services.analysis_engine import generate_contact_profile, scan_conversation

router = APIRouter()


def _run_analysis_job(contact_id: str, quality_mode=None) -> None:
    """Background task that runs the full windowed analysis pipeline."""
    from app.db.session import SessionLocal
    from app.models import Contact

    db = SessionLocal()
    try:
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            return
        contact.analysis_status = "processing"
        db.commit()
        try:
            generate_contact_profile(db, contact, quality_mode=quality_mode)
            contact.analysis_status = "completed"
            contact.analysis_error = None
        except Exception as exc:
            contact.analysis_status = "failed"
            contact.analysis_error = str(exc)[:500]
        db.commit()
    finally:
        db.close()


@router.post(
    "/{contact_id}/analysis/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
)
def regenerate_analysis(
    contact_id: str,
    background_tasks: BackgroundTasks,
    payload: AnalysisRegenerateRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Queue the full windowed reading pipeline as a background job.
    Returns 202 immediately. Frontend polls /analysis/status for progress.
    """
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    contact.analysis_status = "processing"
    contact.analysis_error = None
    db.commit()

    background_tasks.add_task(
        _run_analysis_job,
        contact_id,
        quality_mode=payload.quality_mode if payload else None,
    )
    return {
        "status": "processing",
        "message": "Analysis queued. Poll /analysis/status for progress.",
    }


@router.get("/{contact_id}/analysis/status")
def get_analysis_status(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Poll this endpoint to check analysis progress."""
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    return {
        "status": getattr(contact, "analysis_status", None) or ("completed" if contact.profile_data else "pending"),
        "error": getattr(contact, "analysis_error", None),
        "has_profile": contact.profile_data is not None,
        "profile_generated_at": contact.profile_generated_at.isoformat() if contact.profile_generated_at else None,
    }


@router.get("/{contact_id}/analysis/scan")
def scan_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Free scan / teaser endpoint. Returns message stats, pricing tier,
    behavioral snapshot, and up to 3 teaser moments. Cheap to run (~$0.30 max)
    and designed to sit in front of the paywall.
    """
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    return scan_conversation(db, contact)
