from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.contacts import _get_contact_or_404
from app.db.session import get_db
from app.models import Message, User
from app.services.behavioral_intel import compare_contacts

router = APIRouter()


@router.get("/compare")
def compare_two_contacts(
    contact_a: str = Query(...),
    contact_b: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Compare behavioral patterns between two imported contacts.
    Requires both contacts to have messages imported.
    """
    a = _get_contact_or_404(db, current_user.id, contact_a)
    b = _get_contact_or_404(db, current_user.id, contact_b)

    messages_a = list(
        db.scalars(select(Message).where(Message.contact_id == a.id).order_by(Message.timestamp.asc())).all()
    )
    messages_b = list(
        db.scalars(select(Message).where(Message.contact_id == b.id).order_by(Message.timestamp.asc())).all()
    )

    if not messages_a:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No messages imported for {a.name}.")
    if not messages_b:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No messages imported for {b.name}.")

    report = compare_contacts(
        name_a=a.name,
        messages_a=messages_a,
        name_b=b.name,
        messages_b=messages_b,
    )
    return report.to_dict()
