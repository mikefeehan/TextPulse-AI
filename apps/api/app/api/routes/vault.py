from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.contacts import _get_contact_or_404
from app.db.session import get_db
from app.models import Message, MessageTag, User, VaultCategory
from app.schemas.vault import VaultCategoryCreate, VaultCategoryDetail, VaultCategoryRead, VaultMessageCard

router = APIRouter()


@router.get("/{contact_id}/vault/categories", response_model=list[VaultCategoryRead])
def list_vault_categories(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VaultCategoryRead]:
    _get_contact_or_404(db, current_user.id, contact_id)
    categories = db.scalars(
        select(VaultCategory).where(VaultCategory.contact_id == contact_id).order_by(VaultCategory.sort_order.asc())
    ).all()
    counts = Counter(
        tag.category_id
        for tag in db.scalars(
            select(MessageTag).join(Message).where(Message.contact_id == contact_id)
        ).all()
    )
    return [
        VaultCategoryRead(
            id=category.id,
            name=category.name,
            emoji=category.emoji,
            description=category.description,
            count=counts.get(category.id, 0),
            is_default=category.is_default,
            is_active=category.is_active,
        )
        for category in categories
    ]


@router.post("/{contact_id}/vault/categories", response_model=VaultCategoryRead, status_code=status.HTTP_201_CREATED)
def create_vault_category(
    contact_id: str,
    payload: VaultCategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VaultCategoryRead:
    _get_contact_or_404(db, current_user.id, contact_id)
    category = VaultCategory(contact_id=contact_id, **payload.model_dump(), is_default=False, sort_order=999)
    db.add(category)
    db.commit()
    db.refresh(category)
    return VaultCategoryRead(
        id=category.id,
        name=category.name,
        emoji=category.emoji,
        description=category.description,
        count=0,
        is_default=category.is_default,
        is_active=category.is_active,
    )


@router.get("/{contact_id}/vault/categories/{category_id}", response_model=VaultCategoryDetail)
def get_vault_category(
    contact_id: str,
    category_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VaultCategoryDetail:
    _get_contact_or_404(db, current_user.id, contact_id)
    category = db.get(VaultCategory, category_id)
    if category is None or category.contact_id != contact_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")

    tags = db.scalars(
        select(MessageTag).join(Message).where(
            Message.contact_id == contact_id,
            MessageTag.category_id == category_id,
        )
    ).all()
    message_cards = []
    messages = db.scalars(
        select(Message).where(Message.contact_id == contact_id).order_by(Message.timestamp.asc())
    ).all()
    message_index = {message.id: idx for idx, message in enumerate(messages)}
    for tag in tags:
        message = tag.message
        idx = message_index.get(message.id, 0)
        before = [row.message_text[:120] for row in messages[max(0, idx - 2):idx]]
        after = [row.message_text[:120] for row in messages[idx + 1:idx + 3]]
        message_cards.append(
            VaultMessageCard(
                message_id=message.id,
                text=message.message_text,
                timestamp=message.timestamp,
                reasoning=tag.reasoning,
                confidence=tag.confidence,
                context_before=before,
                context_after=after,
            )
        )
    count = len(message_cards)
    return VaultCategoryDetail(
        category=VaultCategoryRead(
            id=category.id,
            name=category.name,
            emoji=category.emoji,
            description=category.description,
            count=count,
            is_default=category.is_default,
            is_active=category.is_active,
        ),
        stats={
            "total_messages": count,
            "first_occurrence": message_cards[0].timestamp.isoformat() if message_cards else "n/a",
            "latest_occurrence": message_cards[-1].timestamp.isoformat() if message_cards else "n/a",
            "share_of_conversation": round((count / max(len(messages), 1)) * 100, 2),
        },
        messages=message_cards,
    )
