from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Contact, ImportRecord, Message, User
from app.schemas.common import MetricExample
from app.schemas.contacts import AnalyticsPayload, ContactCreate, ContactDetail, ContactListItem, ContactSummary, ContactUpdate, ImportSummary
from app.services.analysis_engine import generate_contact_profile
from app.services.analytics import build_contact_analytics
from app.services.imports import ensure_default_categories

router = APIRouter()


@router.get("", response_model=list[ContactListItem])
def list_contacts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ContactListItem]:
    contacts = db.scalars(
        select(Contact).where(Contact.user_id == current_user.id).order_by(Contact.updated_at.desc())
    ).all()
    items: list[ContactListItem] = []
    for contact in contacts:
        messages = db.scalars(
            select(Message).where(Message.contact_id == contact.id).order_by(Message.timestamp.desc())
        ).all()
        imports = db.scalars(select(ImportRecord).where(ImportRecord.contact_id == contact.id)).all()
        items.append(
            ContactListItem(
                **ContactSummary.model_validate(contact).model_dump(),
                latest_message_at=messages[0].timestamp if messages else None,
                message_count=len(messages),
                import_count=len(imports),
                top_takeaway=(contact.profile_data or {}).get("key_takeaways", [{}])[0].get("detail") if contact.profile_data else None,
            )
        )
    return items


@router.post("", response_model=ContactSummary, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContactSummary:
    contact = Contact(user_id=current_user.id, **payload.model_dump())
    db.add(contact)
    db.flush()
    ensure_default_categories(db, contact)
    db.commit()
    db.refresh(contact)
    return ContactSummary.model_validate(contact)


@router.get("/{contact_id}", response_model=ContactDetail)
def get_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContactDetail:
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    messages = db.scalars(
        select(Message).where(Message.contact_id == contact.id).order_by(Message.timestamp.asc())
    ).all()
    analytics = build_contact_analytics(messages)
    imports = db.scalars(
        select(ImportRecord).where(ImportRecord.contact_id == contact.id).order_by(ImportRecord.imported_at.desc())
    ).all()
    recent_messages = [
        MetricExample(message_id=message.id, text=message.message_text[:280], timestamp=message.timestamp, note=message.sender.value)
        for message in messages[-8:]
    ]
    return ContactDetail(
        **ContactSummary.model_validate(contact).model_dump(),
        profile=contact.profile_data,
        analytics=analytics,
        imports=[
            ImportSummary(
                id=item.id,
                source_platform=item.source_platform.value,
                file_name=item.file_name,
                message_count=item.message_count,
                status=item.status.value,
                error_details=item.error_details,
                imported_at=item.imported_at,
                date_range={"start": item.date_range_start, "end": item.date_range_end},
            )
            for item in imports
        ],
        recent_messages=recent_messages,
    )


@router.patch("/{contact_id}", response_model=ContactSummary)
def update_contact(
    contact_id: str,
    payload: ContactUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContactSummary:
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, key, value)
    db.commit()
    db.refresh(contact)
    return ContactSummary.model_validate(contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    db.delete(contact)
    db.commit()


@router.get("/{contact_id}/analytics", response_model=AnalyticsPayload)
def get_contact_analytics(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalyticsPayload:
    contact = _get_contact_or_404(db, current_user.id, contact_id)
    messages = db.scalars(
        select(Message).where(Message.contact_id == contact.id).order_by(Message.timestamp.asc())
    ).all()
    return build_contact_analytics(messages)


def _get_contact_or_404(db: Session, user_id: str, contact_id: str) -> Contact:
    contact = db.scalar(
        select(Contact).where(Contact.id == contact_id, Contact.user_id == user_id)
    )
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found.")
    return contact
