from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Contact, Message, QAMessage, QASession
from app.services.analysis_engine import generate_contact_profile
from app.services.llm import ClaudeTask, maybe_generate_text
from app.services.text_utils import cosine_similarity, deterministic_embedding, keyword_counts
from app.schemas.common import AIQualityMode


def create_qa_session(db: Session, contact: Contact) -> QASession:
    session = QASession(contact_id=contact.id)
    db.add(session)
    db.flush()
    return session


def answer_contact_question(
    db: Session,
    contact: Contact,
    session: QASession,
    question: str,
    quality_mode: AIQualityMode | None = None,
) -> dict:
    if not contact.profile_data:
        generate_contact_profile(db, contact, quality_mode=quality_mode)
        db.flush()

    db.add(QAMessage(session_id=session.id, role="user", content=question))
    relevant_messages = retrieve_relevant_messages(db, contact.id, question, limit=5)
    answer = _llm_answer(contact, question, relevant_messages, quality_mode=quality_mode)
    if not answer:
        answer = _fallback_answer(contact, question, relevant_messages)
    assistant_message = QAMessage(session_id=session.id, role="assistant", content=answer)
    db.add(assistant_message)
    db.flush()
    return {
        "session_id": session.id,
        "answer": answer,
        "supporting_examples": [message.message_text[:180] for message in relevant_messages[:3]],
        "cited_messages": [message.id for message in relevant_messages[:3]],
    }


def retrieve_relevant_messages(
    db: Session,
    contact_id: str,
    query: str,
    limit: int = 5,
) -> list[Message]:
    query_embedding = deterministic_embedding(query)
    query_terms = set(keyword_counts([query]).keys())
    messages = db.scalars(
        select(Message).where(Message.contact_id == contact_id).order_by(Message.timestamp.desc())
    ).all()
    scored = []
    for message in messages:
        overlap = len(query_terms.intersection(set(keyword_counts([message.message_text]).keys())))
        similarity = cosine_similarity(query_embedding, message.embedding or [])
        recency_bonus = 0.08 if message == messages[0] else 0.0
        score = (similarity * 1.4) + (overlap * 0.25) + recency_bonus
        scored.append((score, message))
    scored.sort(key=lambda row: row[0], reverse=True)
    return [message for _, message in scored[:limit]]


def _llm_answer(
    contact: Contact,
    question: str,
    relevant_messages: list[Message],
    *,
    quality_mode: AIQualityMode | None = None,
) -> str | None:
    profile = contact.profile_data or {}
    system_prompt = (
        "You are TextPulse AI, a relationship intelligence assistant. "
        "Answer with warmth, specificity, and grounded behavioral evidence. "
        "Do not diagnose. Reference message evidence directly."
    )
    snippets = "\n".join(
        f"- {message.timestamp.isoformat()}: {message.message_text}" for message in relevant_messages
    )
    user_prompt = (
        f"Contact profile summary: {profile.get('key_takeaways', [])}\n"
        f"Question: {question}\n"
        f"Relevant messages:\n{snippets}\n"
        "Write a practical answer in 2-4 short paragraphs."
    )
    result = maybe_generate_text(
        system_prompt,
        user_prompt,
        task=ClaudeTask.QA,
        max_tokens=900,
        mode=quality_mode,
    )
    return result.content if result else None


def _fallback_answer(contact: Contact, question: str, relevant_messages: list[Message]) -> str:
    takeaways = contact.profile_data.get("key_takeaways", []) if contact.profile_data else []
    lead = takeaways[0]["detail"] if takeaways else "The strongest read comes from their pacing, topic choices, and follow-through."
    examples = " ".join(
        f'On {message.timestamp.strftime("%b %d")}, they said "{message.message_text[:120]}".'
        for message in relevant_messages[:2]
    )
    recommendation = (
        "If you want the cleanest next move, keep your message specific, low-drama, and easy to respond to."
        if any(word in question.lower() for word in ["what should", "how should", "best way", "reply"])
        else "The most reliable signal here is behavior over isolated wording, so read this through consistency and follow-through."
    )
    return f"{lead} {examples} {recommendation}"
