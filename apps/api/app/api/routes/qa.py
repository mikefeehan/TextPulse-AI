from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.contacts import _get_contact_or_404
from app.db.session import get_db
from app.models import QASession, User
from app.schemas.qa import QAReply, QASessionCreateResponse, QASessionRead, QAUserMessageRequest
from app.services.qa import answer_contact_question, create_qa_session

router = APIRouter()


@router.get("/{contact_id}/qa/sessions", response_model=list[QASessionRead])
def list_qa_sessions(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QASessionRead]:
    _get_contact_or_404(db, current_user.id, contact_id)
    sessions = db.scalars(
        select(QASession).where(QASession.contact_id == contact_id).order_by(QASession.created_at.desc())
    ).all()
    return [QASessionRead.model_validate(session) for session in sessions]


@router.post("/{contact_id}/qa/sessions", response_model=QASessionCreateResponse)
def create_session(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QASessionCreateResponse:
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    session = create_qa_session(db, contact)
    db.commit()
    db.refresh(session)
    return QASessionCreateResponse(session=QASessionRead.model_validate(session))


@router.post("/{contact_id}/qa/sessions/{session_id}/messages", response_model=QAReply)
def send_qa_message(
    contact_id: str,
    session_id: str,
    payload: QAUserMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QAReply:
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    session = db.get(QASession, session_id)
    if session is None or session.contact_id != contact.id:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    reply = answer_contact_question(
        db,
        contact,
        session,
        payload.content,
        quality_mode=payload.quality_mode,
    )
    db.commit()
    return QAReply.model_validate(reply)
