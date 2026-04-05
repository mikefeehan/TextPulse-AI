from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import json
from statistics import mean
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Contact, HighlightType, ImportRecord, Message, MessageHighlight, MessageTag, SenderType, VaultCategory
from app.schemas.contacts import (
    AIStrategy,
    ContactProfile,
    DatingSection,
    KeyTakeaway,
    PlaybookDocument,
    ProfileSection,
    ReceiptCard,
    RedGreenFlag,
    TimelineShift,
    ViralSignals,
)
from app.schemas.common import AIQualityMode, MetricExample
from app.services.analytics import build_contact_analytics
from app.services.llm import ClaudeTask, maybe_generate_json, plan_claude_request
from app.services.text_utils import keyword_counts

CATEGORY_KEYWORDS = {
    "Flirty / Sexual": ["cute", "hot", "kiss", "sexy", "miss you", "date", "come over", "turn me on"],
    "Angry / Frustrated": ["annoying", "mad", "upset", "wtf", "frustrated", "angry", "whatever"],
    "Compliments About Me": ["proud of you", "you look", "you're so", "i admire", "amazing"],
    "Advice They Gave": ["you should", "i think you", "my advice", "honestly", "i'd recommend"],
    "Funniest Moments": ["haha", "lmao", "lol", "rofl", "dead", "meme"],
    "Vulnerable / Deep": ["scared", "anxious", "afraid", "hurt", "therapy", "struggling", "overwhelmed"],
    "Affectionate / Sweet": ["love you", "miss you", "thinking of you", "sweet dreams", "take care"],
    "Red Flags": ["gaslight", "crazy", "overreacting", "chill", "relax", "stop being", "you're too much"],
    "Green Flags": ["i understand", "that's fair", "thank you", "i appreciate", "i hear you"],
    "Plans & Promises": ["let's", "we should", "plan", "dinner", "this weekend", "promise", "booked"],
    "Interesting / Insightful": ["i realized", "perspective", "meaning", "insight", "philosophy"],
    "Excuses": ["busy", "sorry i forgot", "something came up", "rain check", "maybe another time"],
    "Apologies": ["sorry", "my bad", "i apologize", "that's on me"],
    "Career / Ambition": ["work", "job", "promotion", "business", "career", "money", "project"],
    "Family / Friends": ["mom", "dad", "sister", "brother", "friend", "family", "roommate"],
    "Boundaries": ["not comfortable", "need space", "not ready", "slow down", "boundary"],
    "Hurtful": ["don't care", "leave me alone", "shut up", "you're embarrassing", "pathetic"],
    "What They Want": ["i want", "looking for", "need", "future", "eventually", "ideally"],
}

OPENNESS_WORDS = {"travel", "art", "novel", "curious", "idea", "adventure", "museum"}
CONSCIENTIOUS_WORDS = {"plan", "schedule", "deadline", "early", "organized", "project"}
EXTRAVERSION_WORDS = {"party", "everyone", "tonight", "fun", "out", "together", "!!!"}
AGREEABLENESS_WORDS = {"thank", "appreciate", "support", "sorry", "understand", "care"}
NEUROTICISM_WORDS = {"anxious", "stressed", "overthink", "worried", "panic", "spiral"}


def generate_contact_profile(
    db: Session,
    contact: Contact,
    quality_mode: AIQualityMode | None = None,
) -> dict:
    messages = db.scalars(
        select(Message).where(Message.contact_id == contact.id).order_by(Message.timestamp.asc())
    ).all()
    imports = db.scalars(
        select(ImportRecord).where(ImportRecord.contact_id == contact.id).order_by(ImportRecord.imported_at.desc())
    ).all()
    categories = db.scalars(select(VaultCategory).where(VaultCategory.contact_id == contact.id)).all()

    if not messages:
        empty_profile = _empty_profile(quality_mode=quality_mode)
        contact.profile_data = empty_profile
        contact.profile_generated_at = datetime.now(UTC)
        return empty_profile

    _retag_messages(db, messages, categories)
    db.flush()
    analytics = build_contact_analytics(messages)
    keywords = keyword_counts([message.message_text for message in messages if message.sender == SenderType.CONTACT])
    big_five = _big_five(messages)
    mbti = _mbti(big_five)
    enneagram = _enneagram(big_five)
    top_topics = [word for word, _ in keywords.most_common(6)]
    favorite_topic = top_topics[0] if top_topics else "shared plans"
    interest_level = _interest_level(
        [message for message in messages if message.sender == SenderType.CONTACT],
        [message for message in messages if message.sender == SenderType.USER],
    )
    red_flags = _build_flag_entries(messages, categories, {"Red Flags", "Excuses", "Hurtful"}, severity="high")
    green_flags = _build_flag_entries(messages, categories, {"Green Flags", "Affectionate / Sweet", "Plans & Promises"}, severity="positive")
    timeline = _build_timeline(messages, analytics)
    freshness = _freshness(messages, imports)

    profile = ContactProfile(
        key_takeaways=[
            KeyTakeaway(
                title="How They Show Up",
                detail=f"They communicate with {'high' if big_five['extraversion'] >= 60 else 'measured'} visible energy and tend to spend their strongest attention on {favorite_topic}.",
            ),
            KeyTakeaway(
                title="Best Timing Window",
                detail=f"They usually feel easiest to engage when the thread is moving naturally; their average reply cadence is about {_format_response_time(analytics.stats.get('avg_contact_response_seconds', 0))}.",
            ),
            KeyTakeaway(
                title="What Lands Well",
                detail=f"They respond best to messages that are {'clear and direct' if big_five['conscientiousness'] >= 55 else 'warm and low-pressure'}, especially when you build off existing momentum.",
            ),
            KeyTakeaway(
                title="What To Avoid",
                detail="Pressure spikes, mixed signals, or vague last-minute asks tend to create colder replies when tension is already present.",
            ),
            KeyTakeaway(
                title="Relationship Read",
                detail=f"The relationship currently reads as {'active and engaged' if interest_level >= 7 else 'mixed but workable' if interest_level >= 5 else 'fragile and inconsistent'} based on initiation, pace, and follow-through.",
            ),
        ],
        personality_overview=ProfileSection(
            summary=(
                f"{contact.name} comes across as a {('curious, exploratory' if big_five['openness'] >= 60 else 'grounded, practical')} communicator with "
                f"{('steady' if big_five['agreeableness'] >= 55 else 'selective')} warmth. The language patterns suggest a likely {mbti} energy and an Enneagram {enneagram} style."
            ),
            examples=_examples_for_messages([message for message in messages if message.sender == SenderType.CONTACT][:3], "Representative tone and personality signal."),
            metrics={
                "big_five": big_five,
                "mbti_estimate": mbti,
                "enneagram_estimate": enneagram,
                "message_sample_size": len(messages),
            },
        ),
        communication_style=ProfileSection(
            summary=(
                f"They average about {int(_avg_length(messages, SenderType.CONTACT))} characters per message, "
                f"{'often matching energy quickly' if analytics.stats.get('avg_contact_response_seconds', 0) < 7_200 else 'sometimes spacing replies out before re-engaging'}. "
                f"The conversation rhythm suggests {'they often drive momentum' if _contact_initiation_share(messages) >= 0.5 else 'they are responsive but not always the one pushing things forward'}."
            ),
            examples=_examples_for_messages(_find_messages(messages, ["!", "?", "haha", "lol"], limit=3), "Signal of tone, pacing, or engagement."),
            metrics={
                "avg_contact_message_length": _avg_length(messages, SenderType.CONTACT),
                "avg_user_message_length": _avg_length(messages, SenderType.USER),
                "avg_contact_response_seconds": analytics.stats.get("avg_contact_response_seconds", 0),
                "avg_user_response_seconds": analytics.stats.get("avg_user_response_seconds", 0),
                "top_topics": top_topics,
            },
        ),
        emotional_landscape=ProfileSection(
            summary=(
                f"They show {'wide' if _sentiment_range(messages) > 0.9 else 'moderate'} emotional range in text. The strongest tension signals cluster around "
                f"{', '.join(top_topics[1:3]) if len(top_topics) > 2 else 'plans, stress, and expectation mismatches'}, while repair tends to work best when messages are calm, specific, and non-accusatory."
            ),
            examples=_examples_for_messages(_find_messages(messages, ["sorry", "stressed", "upset", "need space"], limit=3), "Emotional cue or regulation moment."),
            metrics={
                "emotional_range": round(_sentiment_range(messages), 2),
                "trigger_topics": top_topics[1:4],
                "stress_signals": _stress_patterns(messages),
                "soothers": [
                    "Direct reassurance without over-explaining",
                    "Specific next steps instead of vague repair language",
                    "Giving them room when they explicitly ask for space",
                ],
            },
        ),
        values_and_interests=ProfileSection(
            summary=(
                f"The conversation history suggests their real priorities center on {', '.join(top_topics[:3]) if top_topics else 'connection, routine, and forward motion'}. "
                "They open up most when a topic blends personal stakes with something practical or future-facing."
            ),
            examples=_examples_for_messages(_find_messages(messages, top_topics[:4], limit=3), "Topic that repeatedly pulls longer or more invested responses."),
            metrics={
                "core_values": _core_values(top_topics),
                "passions": top_topics[:5],
                "pet_peeves": _pet_peeves(messages),
            },
        ),
        humor_profile=ProfileSection(
            summary=f"The humor signature reads as {_humor_style(messages)}. Jokes seem to function both as connection and, at times, a way to soften or dodge heavier moments.",
            examples=_examples_for_messages(_find_messages(messages, ["haha", "lol", "lmao", "\ud83d\ude02"], limit=3), "Humor and banter example."),
            metrics={
                "humor_type": _humor_style(messages),
                "inside_jokes": top_topics[:3],
                "laugh_ratio": round(_laugh_ratio(messages), 2),
            },
        ),
        relationship_dynamics=ProfileSection(
            summary=(
                f"The dynamic looks {'fairly balanced' if _message_balance(messages) < len(messages) * 0.15 else 'slightly asymmetrical'}, with "
                f"{'the contact' if _contact_initiation_share(messages) >= 0.5 else 'the user'} more often setting the pace. Trust seems {'to be building' if freshness['latest_message_age_days'] < 14 else 'to need a fresh data refresh'} based on recency and openness."
            ),
            examples=_examples_for_messages(_find_messages(messages, ["miss you", "not ready", "let's", "sorry"], limit=3), "Signal of reciprocity, boundary, or investment."),
            metrics={
                "power_dynamics": "contact-led" if _contact_initiation_share(messages) >= 0.5 else "user-led",
                "investment_level": interest_level,
                "reciprocity_gap": _message_balance(messages),
                "trust_trajectory": "warming" if freshness["latest_message_age_days"] < 21 else "stale",
            },
        ),
        dating_mode=_dating_section(messages, interest_level, top_topics) if contact.is_dating_mode else None,
        red_flags=red_flags,
        green_flags=green_flags,
        timeline_and_evolution=timeline,
        viral_signals=_build_viral_signals(messages, interest_level, top_topics, red_flags, green_flags, big_five),
        freshness=freshness,
        ai_strategy=_build_ai_strategy(quality_mode),
    )

    _apply_llm_profile_synthesis(
        contact=contact,
        profile=profile,
        messages=messages,
        analytics=analytics,
        top_topics=top_topics,
        quality_mode=quality_mode,
    )
    _replace_highlights(db, contact, red_flags, green_flags)
    contact.profile_data = profile.model_dump()
    contact.profile_generated_at = datetime.now(UTC)
    db.flush()
    return contact.profile_data


def _empty_profile(quality_mode: AIQualityMode | None = None) -> dict:
    return ContactProfile(
        key_takeaways=[],
        personality_overview=ProfileSection(summary="Import messages to generate a profile."),
        communication_style=ProfileSection(summary="Import messages to generate a profile."),
        emotional_landscape=ProfileSection(summary="Import messages to generate a profile."),
        values_and_interests=ProfileSection(summary="Import messages to generate a profile."),
        humor_profile=ProfileSection(summary="Import messages to generate a profile."),
        relationship_dynamics=ProfileSection(summary="Import messages to generate a profile."),
        red_flags=[],
        green_flags=[],
        timeline_and_evolution=[],
        viral_signals=ViralSignals(
            ghost_probability=0,
            toxicity_score=0,
            heat_index=0,
            receipt=ReceiptCard(
                headline="No data yet",
                one_line_roast="Upload a conversation to generate a receipt.",
                interest_level=0,
                top_traits=[],
                red_flags=[],
                green_flags=[],
                catchphrases=[],
            ),
            playbook=PlaybookDocument(
                communication_cheat_sheet=[],
                emotional_playbook=[],
                date_planning_intelligence=[],
                conflict_resolution_guide=[],
                advance_moves=[],
                two_week_strategy=[],
                gift_ideas=[],
            ),
        ),
        freshness={"stale": True, "latest_message_age_days": None},
        ai_strategy=_build_ai_strategy(quality_mode, provider="heuristic"),
    ).model_dump()


def _build_ai_strategy(
    quality_mode: AIQualityMode | None,
    *,
    provider: str = "anthropic",
) -> AIStrategy:
    resolved_mode = quality_mode or AIQualityMode.BALANCED
    from app.core.config import get_settings

    settings = get_settings()
    profile_plan = plan_claude_request(
        "Profile synthesis strategy",
        "Condensed relationship intelligence payload",
        task=ClaudeTask.PROFILE_SYNTHESIS,
        max_tokens=1200,
        mode=resolved_mode,
    )
    live_plan = plan_claude_request(
        "Live coaching strategy",
        "Question or incoming message with supporting examples",
        task=ClaudeTask.QA,
        max_tokens=900,
        mode=resolved_mode,
    )
    if not profile_plan or not live_plan:
        return AIStrategy(
            provider="heuristic",
            quality_mode=resolved_mode,
            notes=[
                "No Anthropic API key configured, so the platform is using heuristic intelligence generation.",
            ],
        )
    return AIStrategy(
        provider=provider,
        quality_mode=resolved_mode,
        profile_model=profile_plan.model,
        live_model=live_plan.model,
        budget_profile_usd=settings.anthropic_profile_request_budget_usd,
        budget_live_usd=settings.anthropic_live_request_budget_usd,
        notes=[
            "Bulk analysis stays heuristic and retrieval-driven to control spend.",
            "Claude is reserved for synthesis, live Q&A, and reply coaching.",
            "Model routing automatically downgrades when the estimated request cost exceeds budget.",
        ],
    )


def _apply_llm_profile_synthesis(
    *,
    contact: Contact,
    profile: ContactProfile,
    messages: list[Message],
    analytics,
    top_topics: list[str],
    quality_mode: AIQualityMode | None,
) -> None:
    representative_messages = [
        {
            "timestamp": message.timestamp.isoformat(),
            "sender": message.sender.value,
            "text": message.message_text[:220],
        }
        for message in _representative_messages(messages)
    ]
    digest = {
        "contact_name": contact.name,
        "relationship_type": contact.relationship_type.value,
        "dating_mode": contact.is_dating_mode,
        "sample_size": len(messages),
        "top_topics": top_topics[:6],
        "current_takeaways": [takeaway.model_dump() for takeaway in profile.key_takeaways],
        "behavioral_metrics": {
            "avg_contact_response_seconds": analytics.stats.get("avg_contact_response_seconds", 0),
            "avg_user_response_seconds": analytics.stats.get("avg_user_response_seconds", 0),
            "top_topics": top_topics[:6],
            "heat_index": profile.viral_signals.heat_index,
            "ghost_probability": profile.viral_signals.ghost_probability,
            "toxicity_score": profile.viral_signals.toxicity_score,
        },
        "red_flags": [flag.label for flag in profile.red_flags],
        "green_flags": [flag.label for flag in profile.green_flags],
        "recent_messages": representative_messages,
    }
    result = maybe_generate_json(
        system_prompt=(
            "You are TextPulse AI. Rewrite heuristic relationship analysis into premium, evidence-grounded, "
            "high-signal product copy. Do not diagnose. Do not overclaim certainty. Return strict JSON only."
        ),
        user_prompt=(
            "Return strict JSON with keys: key_takeaways, personality_overview_summary, communication_style_summary, "
            "emotional_landscape_summary, values_and_interests_summary, humor_profile_summary, "
            "relationship_dynamics_summary, dating_mode, receipt_one_line_roast, playbook. "
            "Each takeaway should have title and detail. dating_mode should be null if dating_mode=false; otherwise "
            "return strategic_insights, what_they_seem_to_want, interest_trajectory, and the_play. "
            "playbook should contain arrays for communication_cheat_sheet, emotional_playbook, "
            "date_planning_intelligence, conflict_resolution_guide, advance_moves, two_week_strategy, gift_ideas.\n"
            f"Digest:\n{json.dumps(digest, ensure_ascii=True)}"
        ),
        task=ClaudeTask.PROFILE_SYNTHESIS,
        max_tokens=1400,
        mode=quality_mode,
    )
    if not result:
        return
    _apply_synthesis_payload(profile, result.data)
    profile.ai_strategy = _build_ai_strategy(quality_mode)
    profile.ai_strategy.profile_model = result.plan.model
    profile.ai_strategy.notes.append(
        f"Last profile synthesis estimated request cost: ${result.plan.estimated_cost_usd:.4f}."
    )
    if result.plan.downgraded:
        profile.ai_strategy.notes.append("Profile synthesis was automatically downgraded to stay within the configured budget.")


def _apply_synthesis_payload(profile: ContactProfile, payload: dict[str, object]) -> None:
    takeaways = payload.get("key_takeaways")
    if isinstance(takeaways, list):
        next_takeaways = []
        for item in takeaways[:5]:
            if isinstance(item, dict):
                title = str(item.get("title", "")).strip()
                detail = str(item.get("detail", "")).strip()
                if title and detail:
                    next_takeaways.append(KeyTakeaway(title=title, detail=detail))
        if next_takeaways:
            profile.key_takeaways = next_takeaways

    summary_fields = {
        "personality_overview_summary": profile.personality_overview,
        "communication_style_summary": profile.communication_style,
        "emotional_landscape_summary": profile.emotional_landscape,
        "values_and_interests_summary": profile.values_and_interests,
        "humor_profile_summary": profile.humor_profile,
        "relationship_dynamics_summary": profile.relationship_dynamics,
    }
    for payload_key, section in summary_fields.items():
        value = payload.get(payload_key)
        if isinstance(value, str) and value.strip():
            section.summary = value.strip()

    dating_payload = payload.get("dating_mode")
    if profile.dating_mode and isinstance(dating_payload, dict):
        strategic_insights = dating_payload.get("strategic_insights")
        if isinstance(strategic_insights, list):
            cleaned = [str(item).strip() for item in strategic_insights if str(item).strip()]
            if cleaned:
                profile.dating_mode.strategic_insights = cleaned[:5]
        for field in ("what_they_seem_to_want", "interest_trajectory", "the_play"):
            value = dating_payload.get(field)
            if isinstance(value, str) and value.strip():
                setattr(profile.dating_mode, field, value.strip())

    roast = payload.get("receipt_one_line_roast")
    if isinstance(roast, str) and roast.strip():
        profile.viral_signals.receipt.one_line_roast = roast.strip()

    playbook_payload = payload.get("playbook")
    if isinstance(playbook_payload, dict):
        for field in (
            "communication_cheat_sheet",
            "emotional_playbook",
            "date_planning_intelligence",
            "conflict_resolution_guide",
            "advance_moves",
            "two_week_strategy",
            "gift_ideas",
        ):
            value = playbook_payload.get(field)
            if isinstance(value, list):
                cleaned = [str(item).strip() for item in value if str(item).strip()]
                if cleaned:
                    setattr(profile.viral_signals.playbook, field, cleaned[:5])


def _representative_messages(messages: list[Message]) -> list[Message]:
    chosen: list[Message] = []
    chosen.extend(messages[:2])
    chosen.extend(_find_messages(messages, ["miss you", "busy", "sorry", "let's", "need space", "lol"], limit=4))
    chosen.extend(messages[-2:])
    deduped: list[Message] = []
    seen: set[str] = set()
    for message in chosen:
        if message.id in seen:
            continue
        seen.add(message.id)
        deduped.append(message)
    return deduped[:8]


def _retag_messages(db: Session, messages: list[Message], categories: list[VaultCategory]) -> None:
    if not messages or not categories:
        return

    message_ids = [message.id for message in messages]
    db.execute(delete(MessageTag).where(MessageTag.message_id.in_(message_ids), MessageTag.is_manual.is_(False)))

    category_lookup = {category.name: category for category in categories}
    for message in messages:
        lowered = message.message_text.lower()
        for category_name, keywords in CATEGORY_KEYWORDS.items():
            if category_name not in category_lookup:
                continue
            matches = [keyword for keyword in keywords if keyword in lowered]
            if not matches:
                continue
            db.add(
                MessageTag(
                    message=message,
                    category=category_lookup[category_name],
                    confidence=min(0.95, 0.55 + (len(matches) * 0.1)),
                    reasoning=f"Matched {', '.join(matches[:2])} in the message text.",
                    is_manual=False,
                )
            )


def _big_five(messages: list[Message]) -> dict[str, int]:
    contact_texts = [message.message_text for message in messages if message.sender == SenderType.CONTACT]
    all_text = " ".join(contact_texts).lower()
    avg_length = mean([len(text) for text in contact_texts]) if contact_texts else 0
    exclamation_ratio = all_text.count("!") / max(len(contact_texts), 1)
    scores = {
        "openness": _score_from_keywords(all_text, OPENNESS_WORDS, base=48, multiplier=6),
        "conscientiousness": _score_from_keywords(all_text, CONSCIENTIOUS_WORDS, base=50, multiplier=5),
        "extraversion": min(
            85,
            max(
                20,
                int(
                    40
                    + (avg_length / 12)
                    + (exclamation_ratio * 5)
                    + _score_from_keywords(all_text, EXTRAVERSION_WORDS, base=0, multiplier=4)
                ),
            ),
        ),
        "agreeableness": _score_from_keywords(all_text, AGREEABLENESS_WORDS, base=47, multiplier=6),
        "neuroticism": _score_from_keywords(all_text, NEUROTICISM_WORDS, base=42, multiplier=7),
    }
    return scores


def _mbti(big_five: dict[str, int]) -> str:
    return (
        ("E" if big_five["extraversion"] >= 55 else "I")
        + ("N" if big_five["openness"] >= 55 else "S")
        + ("F" if big_five["agreeableness"] >= 55 else "T")
        + ("J" if big_five["conscientiousness"] >= 55 else "P")
    )


def _enneagram(big_five: dict[str, int]) -> str:
    if big_five["agreeableness"] >= 62:
        return "2w3"
    if big_five["conscientiousness"] >= 62:
        return "3w2"
    if big_five["neuroticism"] >= 60:
        return "6w7"
    if big_five["openness"] >= 60:
        return "7w6"
    return "9w1"


def _score_from_keywords(text: str, keywords: set[str], base: int, multiplier: int) -> int:
    count = sum(text.count(keyword) for keyword in keywords)
    return max(20, min(85, base + (count * multiplier)))


def _examples_for_messages(messages: Iterable[Message], note: str) -> list[MetricExample]:
    return [
        MetricExample(
            message_id=message.id,
            text=message.message_text[:280],
            timestamp=message.timestamp,
            note=note,
        )
        for message in list(messages)[:3]
    ]


def _find_messages(messages: list[Message], needles: list[str], limit: int) -> list[Message]:
    matches = []
    for message in messages:
        lowered = message.message_text.lower()
        if any(needle.lower() in lowered for needle in needles if needle):
            matches.append(message)
        if len(matches) >= limit:
            break
    return matches


def _avg_length(messages: list[Message], sender: SenderType) -> float:
    sender_messages = [len(message.message_text) for message in messages if message.sender == sender]
    return round(mean(sender_messages), 1) if sender_messages else 0.0


def _message_balance(messages: list[Message]) -> int:
    contact_count = len([message for message in messages if message.sender == SenderType.CONTACT])
    user_count = len([message for message in messages if message.sender == SenderType.USER])
    return abs(contact_count - user_count)


def _contact_initiation_share(messages: list[Message]) -> float:
    sessions = defaultdict(lambda: {"user": 0, "contact": 0})
    for message in messages:
        if message.session_id is None:
            continue
        sender_key = "contact" if message.sender == SenderType.CONTACT else "user"
        sessions[message.session_id][sender_key] += 1
    if not sessions:
        return 0.0
    starters = [
        "contact" if session["contact"] >= session["user"] else "user"
        for session in sessions.values()
    ]
    return starters.count("contact") / len(starters)


def _sentiment_range(messages: list[Message]) -> float:
    sentiments = [message.sentiment_score or 0 for message in messages]
    return (max(sentiments) - min(sentiments)) if sentiments else 0.0


def _stress_patterns(messages: list[Message]) -> list[str]:
    stressed = _find_messages(messages, ["stressed", "busy", "overwhelmed", "need space"], limit=5)
    patterns = []
    if any("need space" in message.message_text.lower() for message in stressed):
        patterns.append("Tends to ask for space when overloaded.")
    if any("busy" in message.message_text.lower() for message in stressed):
        patterns.append("Defaults to workload explanations when capacity drops.")
    if not patterns:
        patterns.append("Stress shows up more through shorter replies than direct disclosure.")
    return patterns


def _core_values(top_topics: list[str]) -> list[str]:
    mapping = {
        "family": "Family loyalty",
        "work": "Career progress",
        "travel": "Adventure",
        "project": "Ambition",
        "friend": "Social belonging",
        "future": "Stability",
    }
    values = [mapping[word] for word in top_topics if word in mapping]
    return values[:4] or ["Connection", "Momentum", "Emotional safety"]


def _pet_peeves(messages: list[Message]) -> list[str]:
    triggers = []
    if _find_messages(messages, ["late", "cancel", "busy", "whatever"], limit=1):
        triggers.append("Last-minute changes or vague availability")
    if _find_messages(messages, ["don't do that", "stop", "not comfortable"], limit=1):
        triggers.append("Pressure after a clear boundary")
    return triggers or ["Unclear expectations", "Emotional ambiguity"]


def _humor_style(messages: list[Message]) -> str:
    laughs = _find_messages(messages, ["lol", "lmao", "haha"], limit=20)
    if len(laughs) >= 8:
        return "playful and meme-adjacent"
    if len(laughs) >= 3:
        return "dry with occasional playful release"
    return "light, measured, and mostly situational"


def _laugh_ratio(messages: list[Message]) -> float:
    total = len(messages) or 1
    laughs = len(_find_messages(messages, ["lol", "lmao", "haha"], limit=total))
    return laughs / total


def _interest_level(contact_messages: list[Message], user_messages: list[Message]) -> int:
    if not contact_messages:
        return 0
    responses = [
        message.response_time_seconds
        for message in contact_messages
        if message.response_time_seconds is not None
    ]
    avg_response = mean(responses) if responses else 86_400
    question_ratio = sum("?" in message.message_text for message in contact_messages) / len(contact_messages)
    warmth = mean((message.sentiment_score or 0) for message in contact_messages)
    size_balance = min(1.0, len(contact_messages) / max(len(user_messages), 1))
    raw = 4.2 + (question_ratio * 2.0) + (warmth * 1.8) + (size_balance * 1.6)
    if avg_response < 3_600:
        raw += 1.2
    elif avg_response < 14_400:
        raw += 0.6
    return max(1, min(10, round(raw)))


def _dating_section(messages: list[Message], interest_level: int, top_topics: list[str]) -> DatingSection:
    attraction = []
    if _find_messages(messages, ["cute", "hot", "miss you", "come over"], limit=1):
        attraction.append("Shows attraction through compliments or closeness cues.")
    if _find_messages(messages, ["let's", "this weekend", "see you"], limit=1):
        attraction.append("Future-oriented planning signals real engagement.")
    distance = []
    if _find_messages(messages, ["busy", "maybe", "not sure"], limit=1):
        distance.append("Uses soft ambiguity when not ready to commit to a plan.")
    if _find_messages(messages, ["need space", "later"], limit=1):
        distance.append("Creates distance with pacing language when pressure rises.")
    return DatingSection(
        interest_level_score=interest_level,
        attraction_indicators=attraction or ["Attention shows up more in responsiveness than overt flirtation."],
        distance_indicators=distance or ["No strong pull-back pattern surfaced in the current sample."],
        interest_trajectory="rising" if interest_level >= 7 else "flat" if interest_level >= 5 else "falling",
        what_they_seem_to_want="A connection that feels emotionally easy, low-drama, and directionally clear.",
        strategic_insights=[
            "Keep invites specific and easy to answer.",
            "Mirror their pace instead of over-explaining when energy drops.",
            f"Use {top_topics[0] if top_topics else 'shared interests'} as the easiest bridge into a stronger conversation.",
        ],
        the_play="Reduce extra check-ins, send cleaner invitations, and let positive momentum build around one concrete plan rather than repeated reassurance.",
    )


def _build_flag_entries(
    messages: list[Message],
    categories: list[VaultCategory],
    category_names: set[str],
    severity: str,
) -> list[RedGreenFlag]:
    category_lookup = {category.id: category for category in categories if category.name in category_names}
    flagged: dict[str, list[MessageTag]] = defaultdict(list)
    for message in messages:
        for tag in message.tags:
            if tag.category_id in category_lookup:
                flagged[category_lookup[tag.category_id].name].append(tag)

    entries: list[RedGreenFlag] = []
    for category_name, tags in flagged.items():
        entries.append(
            RedGreenFlag(
                label=category_name,
                severity=severity,
                detail=f"{len(tags)} message(s) matched this pattern.",
                examples=[
                    MetricExample(
                        message_id=tag.message.id,
                        text=tag.message.message_text[:280],
                        timestamp=tag.message.timestamp,
                        note=tag.reasoning,
                    )
                    for tag in tags[:3]
                ],
            )
        )
    return entries[:4]


def _build_timeline(messages: list[Message], analytics) -> list[TimelineShift]:
    timeline = []
    if analytics.message_volume:
        first = analytics.message_volume[0]
        last = analytics.message_volume[-1]
        timeline.append(
            TimelineShift(
                title="Conversation Arc",
                summary=f"Volume moved from {int(first.user_count + first.contact_count)} messages in {first.label} to {int(last.user_count + last.contact_count)} in {last.label}.",
                timestamp=messages[-1].timestamp,
            )
        )
    if analytics.sentiment_trend:
        best = max(analytics.sentiment_trend, key=lambda item: item.contact_count)
        worst = min(analytics.sentiment_trend, key=lambda item: item.contact_count)
        timeline.append(
            TimelineShift(
                title="Emotional Swing",
                summary=f"The warmest month in the current dataset was {best.label}; the coolest stretch was {worst.label}.",
                timestamp=messages[-1].timestamp,
            )
        )
    timeline.append(
        TimelineShift(
            title="Most Recent State",
            summary="Recent messages suggest the current dynamic should be read from pace and follow-through more than from isolated words.",
            timestamp=messages[-1].timestamp,
        )
    )
    return timeline


def _build_viral_signals(
    messages: list[Message],
    interest_level: int,
    top_topics: list[str],
    red_flags: list[RedGreenFlag],
    green_flags: list[RedGreenFlag],
    big_five: dict[str, int],
) -> ViralSignals:
    ghost_probability = min(99, max(8, 45 + ((6 - interest_level) * 7) + (len(red_flags) * 6) - (len(green_flags) * 4)))
    toxicity_score = min(99, max(4, (len(red_flags) * 14) + max(0, 28 - (len(green_flags) * 6))))
    heat_index = min(99, max(12, (interest_level * 8) + len(_find_messages(messages, ["miss you", "cute", "hot", "date"], limit=20)) * 4))
    top_traits = sorted(big_five.items(), key=lambda item: item[1], reverse=True)[:3]
    catchphrases = [word for word in top_topics[:5] if len(word) > 3]
    return ViralSignals(
        ghost_probability=ghost_probability,
        toxicity_score=toxicity_score,
        heat_index=heat_index,
        receipt=ReceiptCard(
            headline="Relationship Receipt",
            one_line_roast="Replies like a mystery novel and a calendar invite had a baby.",
            interest_level=interest_level,
            top_traits=[name.title() for name, _ in top_traits],
            red_flags=[entry.label for entry in red_flags[:3]],
            green_flags=[entry.label for entry in green_flags[:3]],
            catchphrases=catchphrases,
        ),
        playbook=PlaybookDocument(
            communication_cheat_sheet=[
                "Lead with one clear ask or one clear emotional point.",
                "Stay concise unless they are already sending longer replies.",
                "Build on active topics instead of hard pivoting into heavy tension.",
            ],
            emotional_playbook=[
                "Use calm specificity when they are stressed.",
                "When defensiveness shows up, lower the temperature before making your point.",
                "If they ask for space, respect it and re-enter with clarity.",
            ],
            date_planning_intelligence=[
                f"Best hooks right now: {', '.join(top_topics[:3]) if top_topics else 'shared interests and concrete plans'}.",
                "Offer one concrete plan instead of an open-ended maybe.",
            ],
            conflict_resolution_guide=[
                "Avoid stacking complaints into one message.",
                "Reference behavior and impact rather than motive.",
                "Offer the next small repair move explicitly.",
            ],
            advance_moves=[
                "Escalate only when pacing and tone have been warm for several exchanges.",
                "Pull back on reassurance if they are already engaged.",
            ],
            two_week_strategy=[
                "Week 1: re-establish momentum with light but specific touchpoints.",
                "Week 2: convert momentum into one clearer plan or one honest conversation.",
            ],
            gift_ideas=[
                f"Lean into {top_topics[0] if top_topics else 'their most repeated interests'} for anything thoughtful or personal.",
            ],
        ),
    )


def _freshness(messages: list[Message], imports: list[ImportRecord]) -> dict:
    latest_message_at = _ensure_aware(messages[-1].timestamp) if messages else None
    latest_import_at = _ensure_aware(imports[0].imported_at) if imports else None
    age_days = (datetime.now(UTC) - latest_message_at).days if latest_message_at else None
    return {
        "latest_message_at": latest_message_at.isoformat() if latest_message_at else None,
        "latest_import_at": latest_import_at.isoformat() if latest_import_at else None,
        "latest_message_age_days": age_days,
        "stale": age_days is None or age_days > 14,
    }


def _format_response_time(seconds: float | int | None) -> str:
    if not seconds:
        return "roughly same-day"
    if seconds < 3_600:
        return "within the hour"
    if seconds < 28_800:
        return "later that day"
    return "the next day or later"


def _replace_highlights(
    db: Session,
    contact: Contact,
    red_flags: list[RedGreenFlag],
    green_flags: list[RedGreenFlag],
) -> None:
    db.execute(delete(MessageHighlight).where(MessageHighlight.contact_id == contact.id))
    for entry, highlight_type in (
        *[(flag, HighlightType.RED_FLAG) for flag in red_flags],
        *[(flag, HighlightType.GREEN_FLAG) for flag in green_flags],
    ):
        if not entry.examples:
            continue
        example = entry.examples[0]
        db.add(
            MessageHighlight(
                contact_id=contact.id,
                message_id=example.message_id,
                highlight_type=highlight_type,
                description=entry.detail,
                profile_section="red_flags" if highlight_type == HighlightType.RED_FLAG else "green_flags",
            )
        )


def _ensure_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
