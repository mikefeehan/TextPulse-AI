from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Contact, Message, ReplyCoachSession
from app.schemas.common import AIQualityMode
from app.schemas.reply_coach import ReplyOption
from app.services.analysis_engine import generate_contact_profile
from app.services.llm import ClaudeJSONResult, ClaudeTask, maybe_generate_json
from app.services.qa import retrieve_relevant_messages
from app.services.text_utils import sentiment_score


def create_reply_coach_session(
    db: Session,
    contact: Contact,
    incoming_message: str,
    quality_mode: AIQualityMode | None = None,
) -> ReplyCoachSession:
    if not contact.profile_data:
        generate_contact_profile(db, contact, quality_mode=quality_mode)
        db.flush()

    recent = retrieve_relevant_messages(db, contact.id, incoming_message, limit=6)
    llm_payload = _llm_reply(contact, incoming_message, recent, quality_mode=quality_mode)
    if llm_payload:
        response = _persist_llm_response(db, contact, incoming_message, llm_payload.data)
        db.flush()
        return response

    response = _fallback_reply(contact, incoming_message, recent)
    db.add(response)
    db.flush()
    return response


def _llm_reply(
    contact: Contact,
    incoming_message: str,
    recent: list[Message],
    *,
    quality_mode: AIQualityMode | None = None,
) -> ClaudeJSONResult | None:
    snippets = "\n".join(f"- {message.timestamp.isoformat()}: {message.message_text}" for message in recent)
    return maybe_generate_json(
        system_prompt=(
            "You are TextPulse AI reply coach. Return strict JSON with keys: subtext_analysis, "
            "reply_options (array of label, tone, message, what_it_signals, likely_reaction), "
            "danger_zones (array), timing_recommendation, escalation_guidance."
        ),
        user_prompt=(
            f"Profile: {contact.profile_data}\n"
            f"Incoming message: {incoming_message}\n"
            f"Relevant history:\n{snippets}\n"
            "Keep suggestions realistic, concise, and emotionally intelligent."
        ),
        task=ClaudeTask.REPLY_COACH,
        mode=quality_mode,
    )


def _persist_llm_response(
    db: Session,
    contact: Contact,
    incoming_message: str,
    payload: dict,
) -> ReplyCoachSession:
    return ReplyCoachSession(
        contact_id=contact.id,
        incoming_message=incoming_message,
        subtext_analysis=payload.get("subtext_analysis", ""),
        reply_options=payload.get("reply_options", []),
        danger_zones=payload.get("danger_zones", []),
        timing_recommendation=payload.get("timing_recommendation", ""),
        escalation_guidance=payload.get("escalation_guidance", ""),
    )


def _fallback_reply(contact: Contact, incoming_message: str, recent: list[Message]) -> ReplyCoachSession:
    profile = contact.profile_data or {}
    incoming_sentiment = sentiment_score(incoming_message)
    is_cold = incoming_sentiment < -0.15 or any(
        word in incoming_message.lower() for word in ["busy", "later", "can't", "not sure", "space"]
    )
    key_takeaway = profile.get("key_takeaways", [{}])[0].get(
        "detail",
        "Keep the response grounded in their pacing and your current momentum.",
    )
    timing = (
        "Reply once you can be concise and calm. This is better answered thoughtfully than instantly."
        if is_cold
        else "Reply while the thread still feels warm. Same-evening is ideal if you want to keep momentum."
    )
    escalation = (
        "De-escalate slightly. Focus on clarity and emotional safety before pushing for more."
        if is_cold
        else "You can move things forward a bit, but do it with one clean next step rather than too much intensity."
    )
    danger_zones = [
        "Do not send a wall of text if their message is short or emotionally guarded.",
        "Avoid accusatory language or forcing immediate clarity if they are already signaling low bandwidth.",
    ]
    options = [
        ReplyOption(
            label="Safe",
            tone="calm",
            message=_safe_reply(incoming_message),
            what_it_signals="You are steady, respectful, and easy to talk to.",
            likely_reaction="Lower defensiveness and a higher chance of continued conversation.",
        ),
        ReplyOption(
            label="Warm",
            tone="empathetic",
            message=_warm_reply(incoming_message),
            what_it_signals="You noticed the emotional context without getting heavy-handed.",
            likely_reaction="Better emotional openness if they want closeness.",
        ),
        ReplyOption(
            label="Forward",
            tone="direct",
            message=_forward_reply(incoming_message),
            what_it_signals="Confidence and momentum with minimal overthinking.",
            likely_reaction="Best when the energy is still good and they respond to clarity.",
        ),
    ]
    return ReplyCoachSession(
        contact_id=contact.id,
        incoming_message=incoming_message,
        subtext_analysis=f"{key_takeaway} The latest message reads as {'guarded or low-capacity' if is_cold else 'open enough to keep the thread moving'} given the wording and pace.",
        reply_options=[option.model_dump() for option in options],
        danger_zones=danger_zones,
        timing_recommendation=timing,
        escalation_guidance=escalation,
    )


def _safe_reply(incoming_message: str) -> str:
    if "busy" in incoming_message.lower():
        return "No worries, handle your day. We can pick this back up later."
    return "Makes sense. I'm good with keeping it simple and taking it from here."


def _warm_reply(incoming_message: str) -> str:
    if "sorry" in incoming_message.lower():
        return "You're okay. I appreciate you saying that, and we can reset."
    return "Totally get it. I want this to feel easy, not heavy, so we can talk when it works."


def _forward_reply(incoming_message: str) -> str:
    if "weekend" in incoming_message.lower() or "plan" in incoming_message.lower():
        return "Let's lock something simple in. Are you free Thursday night or Saturday afternoon?"
    return "I'm into keeping this moving. Want to pick a time and keep it straightforward?"
