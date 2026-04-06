"""
TextPulse AI analysis engine.

This module is the core intelligence layer. Given a contact's full message
history, it produces a structured profile that the frontend renders as
the relationship read.

Architecture:
    1. Basic stats are computed cheaply (message counts, response times,
       balance, topic keywords). These populate a heuristic baseline.
    2. When an Anthropic API key is configured, the conversation is
       chunked into time-based windows and each window is summarized by
       a fast model (Haiku). This costs ~$0.05 per window.
    3. The window summaries + up to 200 high-signal raw messages are
       handed to a strong model (Sonnet/Opus) which writes the actual
       relationship read. This is the expensive call (~$2-$8) and is
       the one that should be gated behind payment.
    4. When no API key is set, the profile is populated entirely from
       heuristics and is honest about it.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Any, Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    Contact,
    HighlightType,
    ImportRecord,
    Message,
    MessageHighlight,
    MessageTag,
    SenderType,
    VaultCategory,
)
from app.schemas.common import AIQualityMode, MetricExample
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
from app.services.analytics import build_contact_analytics
from app.services.llm import ClaudeTask, maybe_generate_json, maybe_generate_text, plan_claude_request
from app.services.text_utils import keyword_counts

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vault tagging keyword map — used by _retag_messages to auto-categorize
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS: dict[str, list[str]] = {
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

# ---------------------------------------------------------------------------
# Pricing tiers — message count breakpoints and suggested prices
# ---------------------------------------------------------------------------

PRICING_TIERS = [
    {"name": "glance", "label": "Glance", "max_messages": 2_500, "price_usd": 9},
    {"name": "read", "label": "Read", "max_messages": 15_000, "price_usd": 24},
    {"name": "deep_read", "label": "Deep Read", "max_messages": 60_000, "price_usd": 39},
    {"name": "archive", "label": "Archive", "max_messages": 200_000, "price_usd": 59},
    {"name": "epic", "label": "Epic", "max_messages": float("inf"), "price_usd": 89},
]


def get_pricing_tier(message_count: int) -> dict[str, Any]:
    """Return the tier dict for a given message count."""
    for tier in PRICING_TIERS:
        if message_count <= tier["max_messages"]:
            return tier
    return PRICING_TIERS[-1]


# ---------------------------------------------------------------------------
# Free scan / teaser — runs cheaply before paywall
# ---------------------------------------------------------------------------


def scan_conversation(
    db: Session,
    contact: Contact,
    quality_mode: AIQualityMode | None = None,
) -> dict[str, Any]:
    """
    Produce a lightweight teaser for the paywall: message stats, date range,
    top topics, and up to 3 "moments I noticed" one-liners. This should cost
    at most ~$0.30 (one cheap Haiku call) so it can run before payment.
    """
    messages: list[Message] = list(
        db.scalars(
            select(Message).where(Message.contact_id == contact.id).order_by(Message.timestamp.asc())
        ).all()
    )
    if not messages:
        return {
            "message_count": 0,
            "tier": get_pricing_tier(0),
            "date_range": {"start": None, "end": None},
            "top_topics": [],
            "moments": [],
            "balance": {},
        }

    contact_messages = [m for m in messages if m.sender == SenderType.CONTACT]
    user_messages = [m for m in messages if m.sender == SenderType.USER]
    keywords = keyword_counts([m.message_text for m in contact_messages])
    top_topics = [word for word, _ in keywords.most_common(8)]
    tier = get_pricing_tier(len(messages))

    # Pick 3 emotionally-loaded moments for the teaser
    moments = _pick_teaser_moments(messages, contact.name, quality_mode)

    return {
        "message_count": len(messages),
        "contact_message_count": len(contact_messages),
        "user_message_count": len(user_messages),
        "tier": tier,
        "date_range": {
            "start": messages[0].timestamp.isoformat() if messages else None,
            "end": messages[-1].timestamp.isoformat() if messages else None,
        },
        "duration_days": (messages[-1].timestamp - messages[0].timestamp).days if len(messages) > 1 else 0,
        "top_topics": top_topics,
        "moments": moments,
        "balance": {
            "contact_avg_length": round(_avg_length(messages, SenderType.CONTACT), 1),
            "user_avg_length": round(_avg_length(messages, SenderType.USER), 1),
            "contact_initiation_share": round(_contact_initiation_share(messages), 2),
        },
    }


def _pick_teaser_moments(
    messages: list[Message],
    contact_name: str,
    quality_mode: AIQualityMode | None,
) -> list[str]:
    """
    Pick 3 specific moments from the conversation that hint at what the
    full read would contain. Uses a cheap Haiku call if available, otherwise
    falls back to heuristic selection.
    """
    # Grab a handful of high-signal messages for the teaser
    signal_messages = _select_high_signal_messages(messages, limit=30)
    formatted = _format_messages_for_prompt(signal_messages, max_chars=6000)

    result = maybe_generate_json(
        system_prompt=(
            "You are TextPulse AI. You are scanning a conversation to produce a brief teaser. "
            "Return strict JSON: {\"moments\": [\"one-liner 1\", \"one-liner 2\", \"one-liner 3\"]}. "
            "Each moment should be a specific, intriguing one-sentence observation about the "
            "relationship dynamics visible in these messages. Be concrete — reference dates, "
            "patterns, or specific phrases you noticed. Make the reader want to see the full analysis."
        ),
        user_prompt=(
            f"Contact: {contact_name}\n"
            f"Sample messages ({len(signal_messages)} of {len(messages)} total):\n{formatted}"
        ),
        task=ClaudeTask.WINDOW_SUMMARY,
        max_tokens=400,
        mode=quality_mode,
    )
    if result and isinstance(result.data.get("moments"), list):
        return [str(m) for m in result.data["moments"][:3]]

    # Heuristic fallback: surface basic observations
    return _heuristic_teaser_moments(messages)


def _heuristic_teaser_moments(messages: list[Message]) -> list[str]:
    moments: list[str] = []
    if len(messages) > 100:
        first_month = messages[0].timestamp + timedelta(days=30)
        early = [m for m in messages if m.timestamp < first_month]
        late = messages[-30:]
        early_avg = _avg_length(early, SenderType.CONTACT)
        late_avg = _avg_length(late, SenderType.CONTACT)
        if late_avg < early_avg * 0.6:
            moments.append("Their messages got noticeably shorter over time — the energy shifted.")
        elif late_avg > early_avg * 1.4:
            moments.append("They started sending longer, more invested messages as time went on.")
    contact_msgs = [m for m in messages if m.sender == SenderType.CONTACT]
    if contact_msgs:
        longest = max(contact_msgs, key=lambda m: len(m.message_text))
        moments.append(f"Their longest message was {len(longest.message_text)} characters — that's where the real feelings are.")
    gaps = _find_biggest_gaps(messages, top_n=1)
    if gaps:
        gap_days, gap_msg = gaps[0]
        if gap_days > 3:
            moments.append(f"There was a {gap_days}-day silence before one of you reached back out.")
    return moments[:3]


# ---------------------------------------------------------------------------
# Main profile generation
# ---------------------------------------------------------------------------


def generate_contact_profile(
    db: Session,
    contact: Contact,
    quality_mode: AIQualityMode | None = None,
) -> dict:
    messages: list[Message] = list(
        db.scalars(
            select(Message).where(Message.contact_id == contact.id).order_by(Message.timestamp.asc())
        ).all()
    )
    imports: list[ImportRecord] = list(
        db.scalars(
            select(ImportRecord).where(ImportRecord.contact_id == contact.id).order_by(ImportRecord.imported_at.desc())
        ).all()
    )
    categories: list[VaultCategory] = list(
        db.scalars(select(VaultCategory).where(VaultCategory.contact_id == contact.id)).all()
    )

    if not messages:
        empty_profile = _empty_profile(quality_mode=quality_mode)
        contact.profile_data = empty_profile
        contact.profile_generated_at = datetime.now(UTC)
        return empty_profile

    _retag_messages(db, messages, categories)
    db.flush()

    analytics = build_contact_analytics(messages)
    contact_messages = [m for m in messages if m.sender == SenderType.CONTACT]
    user_messages = [m for m in messages if m.sender == SenderType.USER]
    keywords = keyword_counts([m.message_text for m in contact_messages])
    top_topics = [word for word, _ in keywords.most_common(8)]
    interest_level = _interest_level(contact_messages, user_messages)
    red_flags = _build_flag_entries(messages, categories, {"Red Flags", "Excuses", "Hurtful"}, severity="high")
    green_flags = _build_flag_entries(messages, categories, {"Green Flags", "Affectionate / Sweet", "Plans & Promises"}, severity="positive")
    timeline = _build_timeline(messages, analytics)
    freshness = _freshness(messages, imports)

    # Build heuristic baseline profile
    profile = _build_heuristic_profile(
        contact=contact,
        messages=messages,
        contact_messages=contact_messages,
        user_messages=user_messages,
        analytics=analytics,
        top_topics=top_topics,
        interest_level=interest_level,
        red_flags=red_flags,
        green_flags=green_flags,
        timeline=timeline,
        freshness=freshness,
        quality_mode=quality_mode,
    )

    # Run the real LLM-based reading pipeline if configured
    _apply_windowed_reading(
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


# ---------------------------------------------------------------------------
# Heuristic baseline — honest stats, no personality-test theater
# ---------------------------------------------------------------------------


def _build_heuristic_profile(
    *,
    contact: Contact,
    messages: list[Message],
    contact_messages: list[Message],
    user_messages: list[Message],
    analytics,
    top_topics: list[str],
    interest_level: int,
    red_flags: list[RedGreenFlag],
    green_flags: list[RedGreenFlag],
    timeline: list[TimelineShift],
    freshness: dict,
    quality_mode: AIQualityMode | None,
) -> ContactProfile:
    avg_contact_len = _avg_length(messages, SenderType.CONTACT)
    avg_user_len = _avg_length(messages, SenderType.USER)
    contact_initiation = _contact_initiation_share(messages)
    avg_response = analytics.stats.get("avg_contact_response_seconds", 0)

    return ContactProfile(
        key_takeaways=[
            KeyTakeaway(
                title="Conversation Scale",
                detail=(
                    f"{len(messages):,} messages over "
                    f"{(messages[-1].timestamp - messages[0].timestamp).days} days. "
                    f"{'They' if contact_initiation >= 0.5 else 'You'} initiated more often, "
                    f"with an average reply time of {_format_response_time(avg_response)}."
                ),
            ),
            KeyTakeaway(
                title="Message Balance",
                detail=(
                    f"They sent {len(contact_messages):,} messages (avg {int(avg_contact_len)} chars). "
                    f"You sent {len(user_messages):,} (avg {int(avg_user_len)} chars). "
                    f"{'Fairly balanced.' if abs(len(contact_messages) - len(user_messages)) < len(messages) * 0.15 else 'Somewhat asymmetric.'}"
                ),
            ),
            KeyTakeaway(
                title="Top Topics",
                detail=f"The conversation centers on: {', '.join(top_topics[:5]) if top_topics else 'no dominant topics extracted yet'}.",
            ),
        ],
        personality_overview=ProfileSection(
            summary="Full personality read requires the AI analysis pass. The stats below give you the raw picture.",
            metrics={"message_count": len(messages), "duration_days": (messages[-1].timestamp - messages[0].timestamp).days},
        ),
        communication_style=ProfileSection(
            summary=(
                f"They average {int(avg_contact_len)} characters per message and typically reply "
                f"{_format_response_time(avg_response)}. "
                f"{'They tend to drive conversations.' if contact_initiation >= 0.5 else 'You tend to drive conversations.'}"
            ),
            metrics={
                "avg_contact_message_length": avg_contact_len,
                "avg_user_message_length": avg_user_len,
                "avg_contact_response_seconds": avg_response,
                "contact_initiation_share": round(contact_initiation, 2),
            },
        ),
        emotional_landscape=ProfileSection(
            summary="Emotional arc analysis requires the AI reading pass.",
            metrics={"sentiment_range": round(_sentiment_range(messages), 2)},
        ),
        values_and_interests=ProfileSection(
            summary=f"Most discussed: {', '.join(top_topics[:5]) if top_topics else 'insufficient data'}.",
            metrics={"top_topics": top_topics[:8]},
        ),
        humor_profile=ProfileSection(summary="Humor analysis requires the AI reading pass."),
        relationship_dynamics=ProfileSection(
            summary=(
                f"{'Fairly balanced dynamic' if abs(len(contact_messages) - len(user_messages)) < len(messages) * 0.15 else 'Asymmetric dynamic'}, "
                f"with {'them' if contact_initiation >= 0.5 else 'you'} setting the pace more often."
            ),
            metrics={"interest_level": interest_level, "contact_initiation_share": round(contact_initiation, 2)},
        ),
        dating_mode=_heuristic_dating_section(messages, interest_level, top_topics) if contact.is_dating_mode else None,
        red_flags=red_flags,
        green_flags=green_flags,
        timeline_and_evolution=timeline,
        viral_signals=_build_viral_signals(messages, interest_level, top_topics, red_flags, green_flags),
        freshness=freshness,
        ai_strategy=_build_ai_strategy(quality_mode),
    )


# ---------------------------------------------------------------------------
# High-signal message selection — 200 messages, not 8
# ---------------------------------------------------------------------------


def _select_high_signal_messages(
    messages: list[Message],
    limit: int = 200,
) -> list[Message]:
    """
    Pick up to `limit` messages that carry the most emotional and relational
    signal across the full conversation timeline. The goal is to give the
    synthesis model a genuinely representative sample without sending
    everything.
    """
    if len(messages) <= limit:
        return list(messages)

    candidates: dict[str, Message] = {}

    def _add(msgs: Iterable[Message], tag: str = "") -> None:
        for m in msgs:
            candidates[m.id] = m

    # Conversation bookends (how it started, where it is now)
    _add(messages[:8])
    _add(messages[-15:])

    # Longest messages — where people put in real effort
    by_length = sorted(messages, key=lambda m: len(m.message_text), reverse=True)
    _add(by_length[:40])

    # Sentiment extremes (strongest positive + negative)
    with_sentiment = [m for m in messages if m.sentiment_score is not None]
    if with_sentiment:
        by_sentiment = sorted(with_sentiment, key=lambda m: m.sentiment_score or 0)
        _add(by_sentiment[:20])  # most negative
        _add(by_sentiment[-20:])  # most positive

    # Messages around biggest time gaps (relationship shifts)
    gaps = _find_biggest_gaps(messages, top_n=10)
    for _, gap_msg in gaps:
        idx = next((i for i, m in enumerate(messages) if m.id == gap_msg.id), None)
        if idx is not None:
            _add(messages[max(0, idx - 2) : idx + 3])

    # Questions (engagement signals)
    questions = [m for m in messages if "?" in m.message_text]
    # Prefer longer questions (more thoughtful)
    questions.sort(key=lambda m: len(m.message_text), reverse=True)
    _add(questions[:20])

    # Messages with emotional keywords
    emotional_needles = {"miss you", "love", "sorry", "need space", "hurt", "scared", "happy", "angry", "worried", "proud", "excited", "afraid", "promise", "trust"}
    emotional = [m for m in messages if any(needle in m.message_text.lower() for needle in emotional_needles)]
    _add(emotional[:30])

    # First message after each major gap (conversation restarters)
    for _, gap_msg in gaps:
        _add([gap_msg])

    # Evenly-spaced samples across the timeline to fill remaining slots
    result = sorted(candidates.values(), key=lambda m: m.timestamp)
    if len(result) < limit:
        step = max(1, len(messages) // (limit - len(result)))
        for i in range(0, len(messages), step):
            if messages[i].id not in candidates:
                candidates[messages[i].id] = messages[i]
                result = sorted(candidates.values(), key=lambda m: m.timestamp)
                if len(result) >= limit:
                    break

    return result[:limit]


def _find_biggest_gaps(messages: list[Message], top_n: int = 5) -> list[tuple[int, Message]]:
    """Return (gap_days, first_message_after_gap) for the N largest gaps."""
    if len(messages) < 2:
        return []
    gaps: list[tuple[int, Message]] = []
    for i in range(1, len(messages)):
        delta = (messages[i].timestamp - messages[i - 1].timestamp).total_seconds()
        gap_days = int(delta / 86400)
        if gap_days >= 1:
            gaps.append((gap_days, messages[i]))
    gaps.sort(key=lambda g: g[0], reverse=True)
    return gaps[:top_n]


def _format_messages_for_prompt(
    messages: list[Message],
    max_chars: int = 80_000,
) -> str:
    """Format messages as a timestamped transcript for an LLM prompt."""
    lines: list[str] = []
    total = 0
    for message in messages:
        sender = "YOU" if message.sender == SenderType.USER else "THEM"
        line = f"[{message.timestamp.strftime('%Y-%m-%d %H:%M')}] {sender}: {message.message_text}"
        if total + len(line) > max_chars:
            lines.append(f"... ({len(messages) - len(lines)} messages truncated)")
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Windowed reading pipeline — the core of the real analysis
# ---------------------------------------------------------------------------


def _chunk_into_windows(messages: list[Message]) -> list[tuple[str, list[Message]]]:
    """
    Split messages into time-based windows. Uses monthly buckets for
    conversations over 3 months, weekly for shorter ones.
    """
    if not messages:
        return []

    total_days = (messages[-1].timestamp - messages[0].timestamp).days
    use_weekly = total_days < 90

    windows: dict[str, list[Message]] = defaultdict(list)
    for message in messages:
        if use_weekly:
            # ISO week label
            label = message.timestamp.strftime("%Y-W%V")
        else:
            label = message.timestamp.strftime("%Y-%m")
        windows[label].append(message)

    return sorted(windows.items(), key=lambda w: w[0])


def _summarize_window(
    window_label: str,
    window_messages: list[Message],
    contact_name: str,
    quality_mode: AIQualityMode | None,
) -> str | None:
    """Summarize one time window using a cheap model (Haiku)."""
    formatted = _format_messages_for_prompt(window_messages, max_chars=40_000)
    contact_count = sum(1 for m in window_messages if m.sender == SenderType.CONTACT)
    user_count = len(window_messages) - contact_count

    result = maybe_generate_text(
        system_prompt=(
            "You are analyzing one time window of a text message conversation. "
            "Write a concise 3-5 sentence summary covering: emotional tenor, "
            "topics discussed, how each person was showing up, and any notable "
            "moments or shifts. Include 2-3 direct quotes from the messages "
            "that best capture this window's energy. Be specific, not generic."
        ),
        user_prompt=(
            f"Window: {window_label} | {len(window_messages)} messages "
            f"({contact_count} from {contact_name}, {user_count} from user)\n\n"
            f"{formatted}"
        ),
        task=ClaudeTask.WINDOW_SUMMARY,
        max_tokens=500,
        mode=quality_mode,
    )
    return result.content if result else None


def _apply_windowed_reading(
    *,
    contact: Contact,
    profile: ContactProfile,
    messages: list[Message],
    analytics,
    top_topics: list[str],
    quality_mode: AIQualityMode | None,
) -> None:
    """
    Run the full windowed reading pipeline:
    1. Chunk conversation into time windows
    2. Summarize each window with Haiku (cheap)
    3. Select 200 high-signal raw messages
    4. Feed summaries + messages to Sonnet/Opus for the real read
    """
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.anthropic_api_key:
        return

    windows = _chunk_into_windows(messages)
    if not windows:
        return

    # Step 1: Summarize each window (cheap Haiku calls)
    log.info("Summarizing %d conversation windows for contact %s", len(windows), contact.id)
    window_summaries: list[str] = []
    for label, window_messages in windows:
        summary = _summarize_window(label, window_messages, contact.name, quality_mode)
        if summary:
            window_summaries.append(f"**{label}** ({len(window_messages)} msgs): {summary}")
        else:
            # Fallback: basic stats for this window
            window_summaries.append(
                f"**{label}**: {len(window_messages)} messages exchanged. (Summary unavailable.)"
            )

    # Step 2: Select high-signal messages
    signal_messages = _select_high_signal_messages(messages, limit=200)
    formatted_messages = _format_messages_for_prompt(signal_messages, max_chars=60_000)

    # Step 3: Final synthesis with strong model
    log.info("Running profile synthesis for contact %s with %d window summaries and %d signal messages",
             contact.id, len(window_summaries), len(signal_messages))

    duration_days = (messages[-1].timestamp - messages[0].timestamp).days
    window_text = "\n\n".join(window_summaries)

    synthesis_result = maybe_generate_json(
        system_prompt=_build_synthesis_system_prompt(),
        user_prompt=_build_synthesis_user_prompt(
            contact_name=contact.name,
            relationship_type=contact.relationship_type.value,
            is_dating_mode=contact.is_dating_mode,
            message_count=len(messages),
            duration_days=duration_days,
            window_summaries=window_text,
            signal_messages=formatted_messages,
            top_topics=top_topics,
            analytics_stats=analytics.stats,
        ),
        task=ClaudeTask.PROFILE_SYNTHESIS,
        max_tokens=3000,
        mode=quality_mode,
    )

    if synthesis_result:
        _apply_synthesis_payload(profile, synthesis_result.data)
        profile.ai_strategy = _build_ai_strategy(quality_mode)
        if synthesis_result.plan:
            profile.ai_strategy.profile_model = synthesis_result.plan.model
            profile.ai_strategy.notes.append(
                f"Windowed reading: {len(windows)} windows summarized, "
                f"{len(signal_messages)} signal messages analyzed. "
                f"Estimated cost: ${synthesis_result.plan.estimated_cost_usd:.4f}."
            )


def _build_synthesis_system_prompt() -> str:
    return (
        "You are TextPulse AI. You have been given window-by-window summaries of a real "
        "text message conversation, plus the highest-signal raw messages selected across "
        "the full timeline.\n\n"
        "Your job is to write a genuinely specific, evidence-grounded read of this "
        "relationship. Do NOT produce generic relationship advice. Every claim you make "
        "must be traceable to something in the summaries or messages. If you cannot ground "
        "a claim in evidence, do not make it.\n\n"
        "When you reference a specific moment, quote the actual words used.\n\n"
        "Be emotionally intelligent but honest. If the dynamic is unhealthy, say so "
        "clearly. If one person is more invested than the other, name it. If the energy "
        "shifted at a specific point, pinpoint when and what happened.\n\n"
        "Return strict JSON only."
    )


def _build_synthesis_user_prompt(
    *,
    contact_name: str,
    relationship_type: str,
    is_dating_mode: bool,
    message_count: int,
    duration_days: int,
    window_summaries: str,
    signal_messages: str,
    top_topics: list[str],
    analytics_stats: dict[str, Any],
) -> str:
    schema = (
        "Return JSON with these keys:\n"
        "- key_takeaways: array of {title, detail} — 5 specific, grounded observations\n"
        "- personality_overview_summary: 2-3 sentences on who this person is based on how they text\n"
        "- communication_style_summary: their texting patterns, pacing, energy levels\n"
        "- emotional_landscape_summary: emotional range, what triggers them, how they regulate\n"
        "- values_and_interests_summary: what they actually care about based on the evidence\n"
        "- humor_profile_summary: how humor functions in this conversation\n"
        "- relationship_dynamics_summary: power dynamics, investment balance, trajectory\n"
        "- timeline_shifts: array of {title, summary} — the 3-4 biggest moments where the dynamic changed\n"
        "- receipt_one_line_roast: one punchy sentence that captures this person's texting energy\n"
        "- ghost_probability: 0-99, grounded in actual behavior patterns\n"
        "- heat_index: 0-99, how emotionally/romantically charged the connection reads\n"
    )
    if is_dating_mode:
        schema += (
            "- dating_mode: {strategic_insights: [strings], what_they_seem_to_want: string, "
            "interest_trajectory: string, the_play: string}\n"
        )
    schema += (
        "- playbook: {communication_cheat_sheet: [strings], emotional_playbook: [strings], "
        "date_planning_intelligence: [strings], conflict_resolution_guide: [strings], "
        "advance_moves: [strings], two_week_strategy: [strings], gift_ideas: [strings]}\n"
    )

    return (
        f"Contact: {contact_name} | Relationship: {relationship_type} | "
        f"Dating mode: {'yes' if is_dating_mode else 'no'}\n"
        f"Scale: {message_count:,} messages over {duration_days} days\n"
        f"Top topics: {', '.join(top_topics[:6])}\n"
        f"Avg response time (them): {_format_response_time(analytics_stats.get('avg_contact_response_seconds', 0))}\n"
        f"Avg response time (you): {_format_response_time(analytics_stats.get('avg_user_response_seconds', 0))}\n\n"
        f"=== CONVERSATION TIMELINE (window summaries) ===\n{window_summaries}\n\n"
        f"=== HIGH-SIGNAL MESSAGES ===\n{signal_messages}\n\n"
        f"{schema}"
    )


def _apply_synthesis_payload(profile: ContactProfile, payload: dict[str, Any]) -> None:
    """Apply the LLM synthesis output to the profile, overwriting heuristic defaults."""
    # Key takeaways
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

    # Section summaries
    for field, key in [
        ("personality_overview", "personality_overview_summary"),
        ("communication_style", "communication_style_summary"),
        ("emotional_landscape", "emotional_landscape_summary"),
        ("values_and_interests", "values_and_interests_summary"),
        ("humor_profile", "humor_profile_summary"),
        ("relationship_dynamics", "relationship_dynamics_summary"),
    ]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            getattr(profile, field).summary = value.strip()

    # Timeline shifts from LLM
    shifts = payload.get("timeline_shifts")
    if isinstance(shifts, list):
        llm_timeline = []
        for item in shifts[:5]:
            if isinstance(item, dict):
                title = str(item.get("title", "")).strip()
                summary = str(item.get("summary", "")).strip()
                if title and summary:
                    llm_timeline.append(TimelineShift(title=title, summary=summary))
        if llm_timeline:
            profile.timeline_and_evolution = llm_timeline

    # Viral signals
    ghost = payload.get("ghost_probability")
    if isinstance(ghost, (int, float)):
        profile.viral_signals.ghost_probability = max(0, min(99, int(ghost)))
    heat = payload.get("heat_index")
    if isinstance(heat, (int, float)):
        profile.viral_signals.heat_index = max(0, min(99, int(heat)))

    # Receipt roast
    roast = payload.get("receipt_one_line_roast")
    if isinstance(roast, str) and roast.strip():
        profile.viral_signals.receipt.one_line_roast = roast.strip()

    # Dating mode
    dating = payload.get("dating_mode")
    if isinstance(dating, dict) and profile.dating_mode is not None:
        for attr in ("strategic_insights", "what_they_seem_to_want", "interest_trajectory", "the_play"):
            val = dating.get(attr)
            if val is not None:
                if isinstance(val, list):
                    setattr(profile.dating_mode, attr, [str(v) for v in val])
                else:
                    setattr(profile.dating_mode, attr, str(val))

    # Playbook
    playbook_data = payload.get("playbook")
    if isinstance(playbook_data, dict):
        for field_name in (
            "communication_cheat_sheet", "emotional_playbook", "date_planning_intelligence",
            "conflict_resolution_guide", "advance_moves", "two_week_strategy", "gift_ideas",
        ):
            items = playbook_data.get(field_name)
            if isinstance(items, list):
                setattr(profile.viral_signals.playbook, field_name, [str(i) for i in items[:8]])


# ---------------------------------------------------------------------------
# Shared helpers (stats, formatting, DB operations)
# ---------------------------------------------------------------------------


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
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.anthropic_api_key:
        return AIStrategy(
            provider="heuristic",
            quality_mode=quality_mode,
            notes=["No Anthropic API key configured. Using stats-only heuristic generation."],
        )

    profile_plan = plan_claude_request("", "", task=ClaudeTask.PROFILE_SYNTHESIS, mode=quality_mode)
    live_plan = plan_claude_request("", "", task=ClaudeTask.REPLY_COACH, mode=quality_mode)
    return AIStrategy(
        provider=provider,
        quality_mode=quality_mode,
        profile_model=profile_plan.model if profile_plan else None,
        live_model=live_plan.model if live_plan else None,
        budget_profile_usd=settings.anthropic_profile_request_budget_usd,
        budget_live_usd=settings.anthropic_live_request_budget_usd,
        notes=["Windowed reading pipeline: Haiku for window summaries, Sonnet/Opus for final synthesis."],
    )


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


def _interest_level(contact_messages: list[Message], user_messages: list[Message]) -> int:
    if not contact_messages:
        return 0
    responses = [m.response_time_seconds for m in contact_messages if m.response_time_seconds is not None]
    avg_response = mean(responses) if responses else 86_400
    question_ratio = sum("?" in m.message_text for m in contact_messages) / len(contact_messages)
    warmth = mean((m.sentiment_score or 0) for m in contact_messages)
    size_balance = min(1.0, len(contact_messages) / max(len(user_messages), 1))
    raw = 4.2 + (question_ratio * 2.0) + (warmth * 1.8) + (size_balance * 1.6)
    if avg_response < 3_600:
        raw += 1.2
    elif avg_response < 14_400:
        raw += 0.6
    return max(1, min(10, round(raw)))


def _avg_length(messages: list[Message], sender: SenderType) -> float:
    sender_messages = [len(m.message_text) for m in messages if m.sender == sender]
    return round(mean(sender_messages), 1) if sender_messages else 0.0


def _contact_initiation_share(messages: list[Message]) -> float:
    sessions: dict[str, dict[str, int]] = defaultdict(lambda: {"user": 0, "contact": 0})
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
    sentiments = [m.sentiment_score or 0 for m in messages]
    return (max(sentiments) - min(sentiments)) if sentiments else 0.0


def _build_flag_entries(
    messages: list[Message],
    categories: list[VaultCategory],
    category_names: set[str],
    severity: str,
) -> list[RedGreenFlag]:
    category_lookup = {c.id: c for c in categories if c.name in category_names}
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
    timeline: list[TimelineShift] = []
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
                summary=f"Warmest period: {best.label}. Coolest: {worst.label}.",
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
) -> ViralSignals:
    # Heuristic defaults — will be overwritten by LLM synthesis if available
    ghost_probability = min(99, max(8, 45 + ((6 - interest_level) * 7) + (len(red_flags) * 6) - (len(green_flags) * 4)))
    heat_index = min(99, max(12, interest_level * 9))
    toxicity_score = min(99, max(4, (len(red_flags) * 14) + max(0, 28 - (len(green_flags) * 6))))
    catchphrases = [word for word in top_topics[:5] if len(word) > 3]
    return ViralSignals(
        ghost_probability=ghost_probability,
        toxicity_score=toxicity_score,
        heat_index=heat_index,
        receipt=ReceiptCard(
            headline="Relationship Receipt",
            one_line_roast="Full read generates a personalized one-liner.",
            interest_level=interest_level,
            top_traits=[],
            red_flags=[e.label for e in red_flags[:3]],
            green_flags=[e.label for e in green_flags[:3]],
            catchphrases=catchphrases,
        ),
        playbook=PlaybookDocument(
            communication_cheat_sheet=["Full playbook generates with the AI reading pass."],
            emotional_playbook=[],
            date_planning_intelligence=[],
            conflict_resolution_guide=[],
            advance_moves=[],
            two_week_strategy=[],
            gift_ideas=[],
        ),
    )


def _heuristic_dating_section(
    messages: list[Message],
    interest_level: int,
    top_topics: list[str],
) -> DatingSection:
    return DatingSection(
        interest_level_score=interest_level,
        attraction_indicators=["Full analysis generates specific attraction signals."],
        distance_indicators=["Full analysis generates specific distance signals."],
        interest_trajectory="rising" if interest_level >= 7 else "flat" if interest_level >= 5 else "falling",
        what_they_seem_to_want="Full analysis generates a grounded read on what they want.",
        strategic_insights=["Full analysis generates specific strategic insights."],
        the_play="Full analysis generates a specific play based on the actual conversation.",
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


# Re-export for backward compatibility with imports.py
def ensure_default_categories(db: Session, contact: Contact) -> None:
    from app.seed.default_categories import DEFAULT_VAULT_CATEGORIES
    existing = db.scalars(
        select(VaultCategory).where(VaultCategory.contact_id == contact.id)
    ).all()
    if existing:
        return
    for index, payload in enumerate(DEFAULT_VAULT_CATEGORIES):
        db.add(
            VaultCategory(
                contact_id=contact.id,
                name=payload["name"],
                emoji=payload["emoji"],
                description=payload["description"],
                is_default=True,
                sort_order=index,
            )
        )
    db.flush()
