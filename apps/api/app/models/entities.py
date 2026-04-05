from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import EncryptedJSON, EncryptedString, FlexibleEmbedding
from app.db.base import Base


def generate_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class RelationshipType(str, Enum):
    DATE = "date"
    FRIEND = "friend"
    COWORKER = "coworker"
    FAMILY = "family"
    OTHER = "other"


class ImportPlatform(str, Enum):
    IMESSAGE = "imessage"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    INSTAGRAM = "instagram"
    ANDROID_SMS = "android_sms"
    CSV = "csv"
    SCREENSHOT = "screenshot"
    PASTE = "paste"


class ImportStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SenderType(str, Enum):
    USER = "user"
    CONTACT = "contact"
    SYSTEM = "system"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    LINK = "link"
    REACTION = "reaction"
    SYSTEM = "system"


class HighlightType(str, Enum):
    KEY_MOMENT = "key_moment"
    RED_FLAG = "red_flag"
    GREEN_FLAG = "green_flag"
    HUMOR = "humor"
    VULNERABILITY = "vulnerability"
    CONFLICT = "conflict"
    MILESTONE = "milestone"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    contacts: Mapped[list["Contact"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    relationship_type: Mapped[RelationshipType] = mapped_column(SqlEnum(RelationshipType))
    is_dating_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    profile_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    profile_data: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="contacts")
    imports: Mapped[list["ImportRecord"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    highlights: Mapped[list["MessageHighlight"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    vault_categories: Mapped[list["VaultCategory"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    qa_sessions: Mapped[list["QASession"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    reply_coach_sessions: Mapped[list["ReplyCoachSession"]] = relationship(back_populates="contact", cascade="all, delete-orphan")


class ImportRecord(Base):
    __tablename__ = "imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    source_platform: Mapped[ImportPlatform] = mapped_column(SqlEnum(ImportPlatform))
    file_name: Mapped[str] = mapped_column(String(255))
    file_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    date_range_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_range_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ImportStatus] = mapped_column(SqlEnum(ImportStatus), default=ImportStatus.PROCESSING)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contact: Mapped["Contact"] = relationship(back_populates="imports")
    messages: Mapped[list["Message"]] = relationship(back_populates="import_record")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("contact_id", "canonical_id", name="uq_messages_contact_canonical_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    import_id: Mapped[str | None] = mapped_column(ForeignKey("imports.id", ondelete="SET NULL"), nullable=True, index=True)
    canonical_id: Mapped[str] = mapped_column(String(255), index=True)
    sender: Mapped[SenderType] = mapped_column(SqlEnum(SenderType))
    message_text: Mapped[str] = mapped_column(EncryptedString())
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    message_type: Mapped[MessageType] = mapped_column(SqlEnum(MessageType), default=MessageType.TEXT)
    response_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(FlexibleEmbedding(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contact: Mapped["Contact"] = relationship(back_populates="messages")
    import_record: Mapped[ImportRecord | None] = relationship(back_populates="messages")
    highlights: Mapped[list["MessageHighlight"]] = relationship(back_populates="message", cascade="all, delete-orphan")
    tags: Mapped[list["MessageTag"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class MessageHighlight(Base):
    __tablename__ = "message_highlights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    highlight_type: Mapped[HighlightType] = mapped_column(SqlEnum(HighlightType))
    description: Mapped[str] = mapped_column(Text)
    profile_section: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contact: Mapped["Contact"] = relationship(back_populates="highlights")
    message: Mapped["Message"] = relationship(back_populates="highlights")


class VaultCategory(Base):
    __tablename__ = "vault_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    emoji: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contact: Mapped[Contact | None] = relationship(back_populates="vault_categories")
    tags: Mapped[list["MessageTag"]] = relationship(back_populates="category", cascade="all, delete-orphan")


class MessageTag(Base):
    __tablename__ = "message_tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("vault_categories.id", ondelete="CASCADE"), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[str] = mapped_column(Text)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    message: Mapped["Message"] = relationship(back_populates="tags")
    category: Mapped["VaultCategory"] = relationship(back_populates="tags")


class QASession(Base):
    __tablename__ = "qa_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contact: Mapped["Contact"] = relationship(back_populates="qa_sessions")
    messages: Mapped[list["QAMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class QAMessage(Base):
    __tablename__ = "qa_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("qa_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["QASession"] = relationship(back_populates="messages")


class ReplyCoachSession(Base):
    __tablename__ = "reply_coach_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    incoming_message: Mapped[str] = mapped_column(Text)
    subtext_analysis: Mapped[str] = mapped_column(Text)
    reply_options: Mapped[list] = mapped_column(JSON, default=list)
    danger_zones: Mapped[list] = mapped_column(JSON, default=list)
    timing_recommendation: Mapped[str] = mapped_column(Text)
    escalation_guidance: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contact: Mapped["Contact"] = relationship(back_populates="reply_coach_sessions")
