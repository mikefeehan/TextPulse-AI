from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.contacts import _get_contact_or_404
from app.db.session import get_db
from app.models import User
from app.schemas.reply_coach import ReplyCoachRequest, ReplyCoachResponse
from app.services.reply_coach import create_reply_coach_session

router = APIRouter()


@router.post("/{contact_id}/reply-coach", response_model=ReplyCoachResponse)
def coach_reply(
    contact_id: str,
    payload: ReplyCoachRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReplyCoachResponse:
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    session = create_reply_coach_session(
        db,
        contact,
        payload.incoming_message,
        quality_mode=payload.quality_mode,
    )
    db.commit()
    db.refresh(session)
    return ReplyCoachResponse.model_validate(session)
