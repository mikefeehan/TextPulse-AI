from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.contacts import _get_contact_or_404
from app.db.session import get_db
from app.models import User
from app.schemas.contacts import AnalysisRegenerateRequest, ContactProfile
from app.services.analysis_engine import generate_contact_profile, scan_conversation

router = APIRouter()


@router.post("/{contact_id}/analysis/regenerate", response_model=ContactProfile)
def regenerate_analysis(
    contact_id: str,
    payload: AnalysisRegenerateRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContactProfile:
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    profile = generate_contact_profile(db, contact, quality_mode=payload.quality_mode if payload else None)
    db.commit()
    return ContactProfile.model_validate(profile)


@router.get("/{contact_id}/analysis/scan")
def scan_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Free scan / teaser endpoint. Returns message stats, pricing tier,
    top topics, and up to 3 teaser moments. Cheap to run (~$0.30 max)
    and designed to sit in front of the paywall.
    """
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    return scan_conversation(db, contact)
