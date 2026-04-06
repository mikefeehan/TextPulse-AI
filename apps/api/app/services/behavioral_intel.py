"""
Behavioral intelligence layer — the moat.

Every metric in this module is computed from structured message data, not
guessed by an AI model. These numbers are ground truth: you cannot replicate
them by pasting messages into Claude, because Claude does not have access to
timestamps, response-time deltas, session boundaries, or cross-contact data.

The behavioral fingerprint feeds into both:
    1. The free scan/teaser (shown before the paywall)
    2. The synthesis prompt (so the AI read is grounded in real metrics)
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from statistics import mean, median
from typing import Any

from app.models import Message, SenderType
from app.services.text_utils import NEGATIVE_WORDS, POSITIVE_WORDS, month_bucket, tokenize


# ---------------------------------------------------------------------------
# Emotional vocabulary for breadth scoring
# ---------------------------------------------------------------------------

EMOTIONAL_WORDS: set[str] = (
    POSITIVE_WORDS
    | NEGATIVE_WORDS
    | {
        "afraid", "alone", "anxious", "betrayed", "bitter", "calm", "caring",
        "comfortable", "content", "crushed", "disappointed", "drained",
        "embarrassed", "empty", "frustrated", "grateful", "guilty", "helpless",
        "hopeful", "hurt", "insecure", "inspired", "jealous", "joyful",
        "lonely", "lost", "nervous", "overwhelmed", "passionate", "peaceful",
        "proud", "rejected", "relieved", "resentful", "safe", "scared",
        "secure", "shy", "tender", "thankful", "torn", "trusted",
        "uncomfortable", "vulnerable", "warm",
    }
)

PLAN_WORDS: set[str] = {
    "dinner", "tomorrow", "tonight", "weekend", "friday", "saturday",
    "sunday", "meet", "come", "pick", "reservation", "tickets", "booked",
    "plan", "plans",
}

VAGUE_PLAN_WORDS: set[str] = {
    "sometime", "someday", "eventually", "whenever", "maybe", "possibly",
    "we should", "we could", "one day",
}


# ---------------------------------------------------------------------------
# Core fingerprint dataclass
# ---------------------------------------------------------------------------


@dataclass
class BehavioralFingerprint:
    """Full behavioral read for one contact, computed from ground-truth data."""

    # Scale
    total_messages: int = 0
    contact_messages: int = 0
    user_messages: int = 0
    duration_days: int = 0
    active_days: int = 0
    messages_per_active_day: float = 0.0

    # Response time distribution
    response_time_buckets: dict[str, dict[str, int]] = field(default_factory=dict)
    contact_avg_response_seconds: float = 0.0
    user_avg_response_seconds: float = 0.0
    contact_median_response_seconds: float = 0.0
    user_median_response_seconds: float = 0.0

    # Double-texting (sending 2+ messages before a reply)
    contact_double_text_count: int = 0
    user_double_text_count: int = 0
    contact_double_text_rate: float = 0.0
    user_double_text_rate: float = 0.0

    # Initiation
    contact_initiation_rate: float = 0.0
    user_initiation_rate: float = 0.0
    initiation_trend: list[dict[str, Any]] = field(default_factory=list)

    # Message length
    contact_avg_length: float = 0.0
    user_avg_length: float = 0.0
    length_asymmetry: float = 0.0  # >1 = they write more, <1 = you write more
    length_trend: list[dict[str, Any]] = field(default_factory=list)

    # Engagement signals
    contact_question_ratio: float = 0.0
    user_question_ratio: float = 0.0
    contact_emotional_vocabulary_breadth: float = 0.0
    user_emotional_vocabulary_breadth: float = 0.0

    # Timing patterns
    contact_late_night_ratio: float = 0.0  # % after 10pm
    user_late_night_ratio: float = 0.0
    contact_peak_hours: list[int] = field(default_factory=list)
    user_peak_hours: list[int] = field(default_factory=list)

    # Gap patterns
    median_conversation_gap_hours: float = 0.0
    contact_silence_break_rate: float = 0.0  # % of silences broken by them
    biggest_gap_days: int = 0

    # Plan-making
    contact_plan_ratio: float = 0.0
    user_plan_ratio: float = 0.0
    contact_vague_plan_ratio: float = 0.0
    user_vague_plan_ratio: float = 0.0

    # --- Predictive signals ---

    investment_asymmetry: int = 0  # -100 to +100
    investment_verdict: str = ""
    ghost_risk: int = 0  # 0 to 99
    ghost_risk_factors: list[str] = field(default_factory=list)
    fade_detected: bool = False
    fade_signals: list[str] = field(default_factory=list)
    worth_your_time: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON storage / API response."""
        return {
            "total_messages": self.total_messages,
            "contact_messages": self.contact_messages,
            "user_messages": self.user_messages,
            "duration_days": self.duration_days,
            "active_days": self.active_days,
            "messages_per_active_day": round(self.messages_per_active_day, 1),
            "response_time": {
                "contact_avg_seconds": round(self.contact_avg_response_seconds),
                "user_avg_seconds": round(self.user_avg_response_seconds),
                "contact_median_seconds": round(self.contact_median_response_seconds),
                "user_median_seconds": round(self.user_median_response_seconds),
                "buckets": self.response_time_buckets,
            },
            "double_texting": {
                "contact_count": self.contact_double_text_count,
                "user_count": self.user_double_text_count,
                "contact_rate": round(self.contact_double_text_rate, 3),
                "user_rate": round(self.user_double_text_rate, 3),
            },
            "initiation": {
                "contact_rate": round(self.contact_initiation_rate, 3),
                "user_rate": round(self.user_initiation_rate, 3),
                "trend": self.initiation_trend,
            },
            "message_length": {
                "contact_avg": round(self.contact_avg_length, 1),
                "user_avg": round(self.user_avg_length, 1),
                "asymmetry": round(self.length_asymmetry, 2),
                "trend": self.length_trend,
            },
            "engagement": {
                "contact_question_ratio": round(self.contact_question_ratio, 3),
                "user_question_ratio": round(self.user_question_ratio, 3),
                "contact_emotional_breadth": round(self.contact_emotional_vocabulary_breadth, 3),
                "user_emotional_breadth": round(self.user_emotional_vocabulary_breadth, 3),
            },
            "timing": {
                "contact_late_night_ratio": round(self.contact_late_night_ratio, 3),
                "user_late_night_ratio": round(self.user_late_night_ratio, 3),
                "contact_peak_hours": self.contact_peak_hours,
                "user_peak_hours": self.user_peak_hours,
            },
            "gaps": {
                "median_gap_hours": round(self.median_conversation_gap_hours, 1),
                "contact_silence_break_rate": round(self.contact_silence_break_rate, 3),
                "biggest_gap_days": self.biggest_gap_days,
            },
            "plan_making": {
                "contact_plan_ratio": round(self.contact_plan_ratio, 3),
                "user_plan_ratio": round(self.user_plan_ratio, 3),
                "contact_vague_ratio": round(self.contact_vague_plan_ratio, 3),
                "user_vague_ratio": round(self.user_vague_plan_ratio, 3),
            },
            "predictions": {
                "investment_asymmetry": self.investment_asymmetry,
                "investment_verdict": self.investment_verdict,
                "ghost_risk": self.ghost_risk,
                "ghost_risk_factors": self.ghost_risk_factors,
                "fade_detected": self.fade_detected,
                "fade_signals": self.fade_signals,
                "worth_your_time": self.worth_your_time,
            },
        }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def compute_behavioral_fingerprint(messages: list[Message]) -> BehavioralFingerprint:
    """
    Compute a full behavioral fingerprint from a contact's message history.
    Every number is ground truth from the structured data.
    """
    fp = BehavioralFingerprint()
    if not messages:
        return fp

    contact_msgs = [m for m in messages if m.sender == SenderType.CONTACT]
    user_msgs = [m for m in messages if m.sender == SenderType.USER]

    fp.total_messages = len(messages)
    fp.contact_messages = len(contact_msgs)
    fp.user_messages = len(user_msgs)
    fp.duration_days = max(1, (messages[-1].timestamp - messages[0].timestamp).days)
    fp.active_days = len({m.timestamp.date() for m in messages})
    fp.messages_per_active_day = fp.total_messages / max(fp.active_days, 1)

    _compute_response_times(fp, contact_msgs, user_msgs)
    _compute_double_texting(fp, messages)
    _compute_initiation(fp, messages)
    _compute_message_lengths(fp, messages, contact_msgs, user_msgs)
    _compute_engagement(fp, contact_msgs, user_msgs)
    _compute_timing(fp, contact_msgs, user_msgs)
    _compute_gaps(fp, messages)
    _compute_plan_making(fp, contact_msgs, user_msgs)

    # Predictive signals (derived from the above)
    _compute_investment_asymmetry(fp)
    _compute_ghost_risk(fp, messages)
    _compute_fade_detection(fp, messages)
    _compute_worth_your_time(fp)

    return fp


# ---------------------------------------------------------------------------
# Comparison (compatibility between two contacts)
# ---------------------------------------------------------------------------


@dataclass
class CompatibilityReport:
    """Comparison of two contacts' behavioral fingerprints."""

    contact_a_name: str
    contact_b_name: str
    timing_compatibility: float = 0.0  # 0-100
    pacing_compatibility: float = 0.0  # 0-100
    effort_compatibility: float = 0.0  # 0-100
    topic_overlap: float = 0.0  # 0-100
    overall_compatibility: float = 0.0  # 0-100
    insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contact_a": self.contact_a_name,
            "contact_b": self.contact_b_name,
            "timing_compatibility": round(self.timing_compatibility, 1),
            "pacing_compatibility": round(self.pacing_compatibility, 1),
            "effort_compatibility": round(self.effort_compatibility, 1),
            "topic_overlap": round(self.topic_overlap, 1),
            "overall_compatibility": round(self.overall_compatibility, 1),
            "insights": self.insights,
        }


def compare_contacts(
    *,
    name_a: str,
    messages_a: list[Message],
    name_b: str,
    messages_b: list[Message],
) -> CompatibilityReport:
    """Compare behavioral patterns between two contacts."""
    fp_a = compute_behavioral_fingerprint(messages_a)
    fp_b = compute_behavioral_fingerprint(messages_b)
    report = CompatibilityReport(contact_a_name=name_a, contact_b_name=name_b)

    # Timing compatibility: do they text at similar hours?
    if fp_a.contact_peak_hours and fp_b.contact_peak_hours:
        overlap = len(set(fp_a.contact_peak_hours) & set(fp_b.contact_peak_hours))
        report.timing_compatibility = min(100, (overlap / max(len(fp_a.contact_peak_hours), 1)) * 100)

    # Pacing compatibility: similar response times?
    if fp_a.contact_avg_response_seconds > 0 and fp_b.contact_avg_response_seconds > 0:
        ratio = min(fp_a.contact_avg_response_seconds, fp_b.contact_avg_response_seconds) / max(
            fp_a.contact_avg_response_seconds, fp_b.contact_avg_response_seconds
        )
        report.pacing_compatibility = ratio * 100

    # Effort compatibility: similar message lengths and question ratios?
    if fp_a.contact_avg_length > 0 and fp_b.contact_avg_length > 0:
        length_ratio = min(fp_a.contact_avg_length, fp_b.contact_avg_length) / max(
            fp_a.contact_avg_length, fp_b.contact_avg_length
        )
        q_diff = abs(fp_a.contact_question_ratio - fp_b.contact_question_ratio)
        report.effort_compatibility = (length_ratio * 70) + ((1 - min(q_diff * 5, 1)) * 30)

    # Topic overlap: Jaccard similarity of top words
    topics_a = {m.message_text.lower() for m in messages_a[:500]}
    topics_b = {m.message_text.lower() for m in messages_b[:500]}
    words_a = set()
    words_b = set()
    for t in topics_a:
        words_a.update(tokenize(t))
    for t in topics_b:
        words_b.update(tokenize(t))
    if words_a and words_b:
        jaccard = len(words_a & words_b) / len(words_a | words_b)
        report.topic_overlap = jaccard * 100

    report.overall_compatibility = mean([
        report.timing_compatibility,
        report.pacing_compatibility,
        report.effort_compatibility,
        report.topic_overlap,
    ])

    # Generate insights
    if fp_a.investment_asymmetry < -30:
        report.insights.append(f"You're significantly more invested in {name_a} than they are in you.")
    if fp_b.investment_asymmetry > 30:
        report.insights.append(f"{name_b} seems more invested in the relationship than you are.")
    if report.pacing_compatibility > 80:
        report.insights.append(f"{name_a} and {name_b} reply at similar speeds — natural rhythm match.")
    if report.pacing_compatibility < 40:
        report.insights.append(f"Big pacing gap: one replies much faster than the other.")
    if report.timing_compatibility > 70:
        report.insights.append("Both tend to be active at similar times of day — easy scheduling.")

    return report


# ---------------------------------------------------------------------------
# Internal computation functions
# ---------------------------------------------------------------------------


RESPONSE_BUCKETS = [
    ("<5m", 0, 300),
    ("5-30m", 300, 1_800),
    ("30m-2h", 1_800, 7_200),
    ("2-8h", 7_200, 28_800),
    ("8h+", 28_800, float("inf")),
]


def _compute_response_times(fp: BehavioralFingerprint, contact_msgs: list[Message], user_msgs: list[Message]) -> None:
    contact_times = [m.response_time_seconds for m in contact_msgs if m.response_time_seconds is not None]
    user_times = [m.response_time_seconds for m in user_msgs if m.response_time_seconds is not None]

    if contact_times:
        fp.contact_avg_response_seconds = mean(contact_times)
        fp.contact_median_response_seconds = median(contact_times)
    if user_times:
        fp.user_avg_response_seconds = mean(user_times)
        fp.user_median_response_seconds = median(user_times)

    buckets: dict[str, dict[str, int]] = {}
    for label, _, _ in RESPONSE_BUCKETS:
        buckets[label] = {"contact": 0, "user": 0}
    for t in contact_times:
        for label, lo, hi in RESPONSE_BUCKETS:
            if lo <= t < hi:
                buckets[label]["contact"] += 1
                break
    for t in user_times:
        for label, lo, hi in RESPONSE_BUCKETS:
            if lo <= t < hi:
                buckets[label]["user"] += 1
                break
    fp.response_time_buckets = buckets


def _compute_double_texting(fp: BehavioralFingerprint, messages: list[Message]) -> None:
    """Count how often each person sends 2+ messages before the other replies."""
    if len(messages) < 3:
        return
    contact_doubles = 0
    user_doubles = 0
    streak_sender = messages[0].sender
    streak_len = 1

    for m in messages[1:]:
        if m.sender == streak_sender:
            streak_len += 1
        else:
            if streak_len >= 2:
                if streak_sender == SenderType.CONTACT:
                    contact_doubles += 1
                else:
                    user_doubles += 1
            streak_sender = m.sender
            streak_len = 1
    # Final streak
    if streak_len >= 2:
        if streak_sender == SenderType.CONTACT:
            contact_doubles += 1
        else:
            user_doubles += 1

    fp.contact_double_text_count = contact_doubles
    fp.user_double_text_count = user_doubles
    total_turns = max(contact_doubles + user_doubles, 1)
    fp.contact_double_text_rate = contact_doubles / max(fp.contact_messages, 1)
    fp.user_double_text_rate = user_doubles / max(fp.user_messages, 1)


def _compute_initiation(fp: BehavioralFingerprint, messages: list[Message]) -> None:
    """Who starts conversations, and how is that trending?"""
    sessions: dict[str | None, Message] = {}
    for m in messages:
        if m.session_id is not None and m.session_id not in sessions:
            sessions[m.session_id] = m

    if not sessions:
        return

    contact_starts = sum(1 for m in sessions.values() if m.sender == SenderType.CONTACT)
    user_starts = len(sessions) - contact_starts
    total = len(sessions)
    fp.contact_initiation_rate = contact_starts / total
    fp.user_initiation_rate = user_starts / total

    # Monthly trend
    monthly: dict[str, dict[str, int]] = defaultdict(lambda: {"contact": 0, "user": 0})
    for m in sessions.values():
        month = month_bucket(m.timestamp)
        if m.sender == SenderType.CONTACT:
            monthly[month]["contact"] += 1
        else:
            monthly[month]["user"] += 1

    fp.initiation_trend = [
        {"month": month, "contact_rate": round(v["contact"] / max(v["contact"] + v["user"], 1), 3)}
        for month, v in sorted(monthly.items())
    ]


def _compute_message_lengths(
    fp: BehavioralFingerprint,
    messages: list[Message],
    contact_msgs: list[Message],
    user_msgs: list[Message],
) -> None:
    contact_lens = [len(m.message_text) for m in contact_msgs]
    user_lens = [len(m.message_text) for m in user_msgs]

    fp.contact_avg_length = mean(contact_lens) if contact_lens else 0.0
    fp.user_avg_length = mean(user_lens) if user_lens else 0.0
    fp.length_asymmetry = fp.contact_avg_length / max(fp.user_avg_length, 1)

    # Monthly trend
    monthly: dict[str, dict[str, list[int]]] = defaultdict(lambda: {"contact": [], "user": []})
    for m in messages:
        month = month_bucket(m.timestamp)
        key = "contact" if m.sender == SenderType.CONTACT else "user"
        monthly[month][key].append(len(m.message_text))

    fp.length_trend = [
        {
            "month": month,
            "contact_avg": round(mean(v["contact"]), 1) if v["contact"] else 0,
            "user_avg": round(mean(v["user"]), 1) if v["user"] else 0,
        }
        for month, v in sorted(monthly.items())
    ]


def _compute_engagement(fp: BehavioralFingerprint, contact_msgs: list[Message], user_msgs: list[Message]) -> None:
    # Question ratio
    if contact_msgs:
        fp.contact_question_ratio = sum(1 for m in contact_msgs if "?" in m.message_text) / len(contact_msgs)
    if user_msgs:
        fp.user_question_ratio = sum(1 for m in user_msgs if "?" in m.message_text) / len(user_msgs)

    # Emotional vocabulary breadth
    fp.contact_emotional_vocabulary_breadth = _emotional_breadth(contact_msgs)
    fp.user_emotional_vocabulary_breadth = _emotional_breadth(user_msgs)


def _emotional_breadth(messages: list[Message]) -> float:
    """Unique emotional words / total words. Higher = more emotionally expressive."""
    if not messages:
        return 0.0
    all_tokens: list[str] = []
    emotional_unique: set[str] = set()
    for m in messages:
        tokens = tokenize(m.message_text)
        all_tokens.extend(tokens)
        for t in tokens:
            if t in EMOTIONAL_WORDS:
                emotional_unique.add(t)
    if not all_tokens:
        return 0.0
    return len(emotional_unique) / math.sqrt(max(len(all_tokens), 1))


def _compute_timing(fp: BehavioralFingerprint, contact_msgs: list[Message], user_msgs: list[Message]) -> None:
    # Late night ratio (after 10pm)
    if contact_msgs:
        fp.contact_late_night_ratio = sum(1 for m in contact_msgs if m.timestamp.hour >= 22) / len(contact_msgs)
    if user_msgs:
        fp.user_late_night_ratio = sum(1 for m in user_msgs if m.timestamp.hour >= 22) / len(user_msgs)

    # Peak hours (top 3)
    fp.contact_peak_hours = _peak_hours(contact_msgs)
    fp.user_peak_hours = _peak_hours(user_msgs)


def _peak_hours(messages: list[Message]) -> list[int]:
    if not messages:
        return []
    counter: Counter[int] = Counter(m.timestamp.hour for m in messages)
    return [hour for hour, _ in counter.most_common(3)]


def _compute_gaps(fp: BehavioralFingerprint, messages: list[Message]) -> None:
    if len(messages) < 2:
        return

    # Find conversation gaps (> 4 hours between messages)
    gaps: list[tuple[float, Message]] = []
    for i in range(1, len(messages)):
        delta = (messages[i].timestamp - messages[i - 1].timestamp).total_seconds()
        if delta > 4 * 3600:  # 4 hours = new conversation
            gaps.append((delta, messages[i]))

    if gaps:
        gap_hours = [g[0] / 3600 for g in gaps]
        fp.median_conversation_gap_hours = median(gap_hours)
        fp.biggest_gap_days = int(max(gap_hours) / 24)

        # Who breaks the silence?
        contact_breaks = sum(1 for _, m in gaps if m.sender == SenderType.CONTACT)
        fp.contact_silence_break_rate = contact_breaks / len(gaps)


def _compute_plan_making(fp: BehavioralFingerprint, contact_msgs: list[Message], user_msgs: list[Message]) -> None:
    fp.contact_plan_ratio = _plan_ratio(contact_msgs, PLAN_WORDS)
    fp.user_plan_ratio = _plan_ratio(user_msgs, PLAN_WORDS)
    fp.contact_vague_plan_ratio = _plan_ratio(contact_msgs, VAGUE_PLAN_WORDS)
    fp.user_vague_plan_ratio = _plan_ratio(user_msgs, VAGUE_PLAN_WORDS)


def _plan_ratio(messages: list[Message], keywords: set[str]) -> float:
    if not messages:
        return 0.0
    hits = sum(1 for m in messages if any(k in m.message_text.lower() for k in keywords))
    return hits / len(messages)


# ---------------------------------------------------------------------------
# Predictive signals
# ---------------------------------------------------------------------------


def _compute_investment_asymmetry(fp: BehavioralFingerprint) -> None:
    """
    -100 to +100. Negative = you're more invested. Positive = they are.
    Composite of 6 independent behavioral metrics.
    """
    signals: list[float] = []

    # 1. Initiation balance (-1 to +1, positive = they initiate more)
    if fp.contact_initiation_rate + fp.user_initiation_rate > 0:
        signals.append((fp.contact_initiation_rate - fp.user_initiation_rate) * 2)

    # 2. Message length ratio
    if fp.user_avg_length > 0:
        ratio = fp.contact_avg_length / fp.user_avg_length
        signals.append(max(-1, min(1, (ratio - 1) * 2)))

    # 3. Response speed (faster = more invested)
    if fp.contact_avg_response_seconds > 0 and fp.user_avg_response_seconds > 0:
        speed_ratio = fp.user_avg_response_seconds / fp.contact_avg_response_seconds
        signals.append(max(-1, min(1, (speed_ratio - 1) * 0.5)))

    # 4. Question ratio
    q_diff = fp.contact_question_ratio - fp.user_question_ratio
    signals.append(max(-1, min(1, q_diff * 5)))

    # 5. Double-text balance
    dt_diff = fp.contact_double_text_rate - fp.user_double_text_rate
    signals.append(max(-1, min(1, dt_diff * 10)))

    # 6. Silence-breaking
    if fp.contact_silence_break_rate > 0:
        signals.append((fp.contact_silence_break_rate - 0.5) * 2)

    if not signals:
        fp.investment_asymmetry = 0
        fp.investment_verdict = "Insufficient data."
        return

    raw = mean(signals) * 100
    fp.investment_asymmetry = max(-100, min(100, int(raw)))

    if fp.investment_asymmetry > 30:
        fp.investment_verdict = "They're clearly more invested than you are."
    elif fp.investment_asymmetry > 10:
        fp.investment_verdict = "Slightly tilted in their direction — they put in a bit more."
    elif fp.investment_asymmetry > -10:
        fp.investment_verdict = "Roughly balanced. Neither person is doing all the work."
    elif fp.investment_asymmetry > -30:
        fp.investment_verdict = "You're putting in more effort than they are."
    else:
        fp.investment_verdict = "Significantly one-sided. You're carrying this."


def _compute_ghost_risk(fp: BehavioralFingerprint, messages: list[Message]) -> None:
    """
    Ghost risk based on trailing behavioral trends, not formula guessing.
    Looks at the last 30 days vs. prior 30 days.
    """
    if len(messages) < 20:
        fp.ghost_risk = 0
        return

    factors: list[str] = []
    risk = 0

    # Trailing response time trend
    recent = messages[-30:]
    contact_recent = [m for m in recent if m.sender == SenderType.CONTACT]
    recent_times = [m.response_time_seconds for m in contact_recent if m.response_time_seconds is not None]

    if recent_times and fp.contact_avg_response_seconds > 0:
        recent_avg = mean(recent_times)
        if recent_avg > fp.contact_avg_response_seconds * 1.5:
            risk += 20
            factors.append("Response times are getting slower recently.")

    # Trailing message frequency
    if fp.duration_days > 60:
        last_30_count = sum(1 for m in messages if m.sender == SenderType.CONTACT and (messages[-1].timestamp - m.timestamp).days < 30)
        prior_30_count = sum(1 for m in messages if m.sender == SenderType.CONTACT and 30 <= (messages[-1].timestamp - m.timestamp).days < 60)
        if prior_30_count > 0 and last_30_count < prior_30_count * 0.5:
            risk += 25
            factors.append("They're sending significantly fewer messages than last month.")

    # Message shortening trend
    if fp.length_trend and len(fp.length_trend) >= 2:
        recent_len = fp.length_trend[-1].get("contact_avg", 0)
        prior_len = mean([t.get("contact_avg", 0) for t in fp.length_trend[:-1]]) if len(fp.length_trend) > 1 else 0
        if prior_len > 0 and recent_len < prior_len * 0.6:
            risk += 15
            factors.append("Their messages are getting noticeably shorter.")

    # Low initiation
    if fp.contact_initiation_rate < 0.2:
        risk += 15
        factors.append("They almost never start conversations.")

    # Investment asymmetry
    if fp.investment_asymmetry < -40:
        risk += 15
        factors.append("The effort balance is heavily one-sided.")

    fp.ghost_risk = min(99, max(0, risk))
    fp.ghost_risk_factors = factors


def _compute_fade_detection(fp: BehavioralFingerprint, messages: list[Message]) -> None:
    """
    Compare last 30 days to prior 30 days on 5 key metrics.
    Flag if 3+ are declining.
    """
    if fp.duration_days < 45 or len(messages) < 50:
        return

    cutoff = messages[-1].timestamp - timedelta(days=30)
    recent = [m for m in messages if m.timestamp >= cutoff]
    prior = [m for m in messages if cutoff - timedelta(days=30) <= m.timestamp < cutoff]

    if len(recent) < 10 or len(prior) < 10:
        return

    declining: list[str] = []

    # 1. Message frequency
    recent_contact = sum(1 for m in recent if m.sender == SenderType.CONTACT)
    prior_contact = sum(1 for m in prior if m.sender == SenderType.CONTACT)
    if prior_contact > 0 and recent_contact < prior_contact * 0.7:
        declining.append("Message frequency dropped by 30%+.")

    # 2. Average message length
    recent_lens = [len(m.message_text) for m in recent if m.sender == SenderType.CONTACT]
    prior_lens = [len(m.message_text) for m in prior if m.sender == SenderType.CONTACT]
    if recent_lens and prior_lens:
        if mean(recent_lens) < mean(prior_lens) * 0.7:
            declining.append("Their messages are getting shorter.")

    # 3. Response speed
    recent_times = [m.response_time_seconds for m in recent if m.sender == SenderType.CONTACT and m.response_time_seconds]
    prior_times = [m.response_time_seconds for m in prior if m.sender == SenderType.CONTACT and m.response_time_seconds]
    if recent_times and prior_times:
        if mean(recent_times) > mean(prior_times) * 1.5:
            declining.append("Replies are taking longer.")

    # 4. Question ratio
    recent_q = sum(1 for m in recent if m.sender == SenderType.CONTACT and "?" in m.message_text)
    prior_q = sum(1 for m in prior if m.sender == SenderType.CONTACT and "?" in m.message_text)
    if prior_q > 2 and recent_q < prior_q * 0.5:
        declining.append("They're asking fewer questions.")

    # 5. Initiation
    recent_inits = sum(1 for m in recent if m.sender == SenderType.CONTACT and m.session_id)
    prior_inits = sum(1 for m in prior if m.sender == SenderType.CONTACT and m.session_id)
    if prior_inits > 2 and recent_inits < prior_inits * 0.5:
        declining.append("They're starting fewer conversations.")

    fp.fade_signals = declining
    fp.fade_detected = len(declining) >= 3


def _compute_worth_your_time(fp: BehavioralFingerprint) -> None:
    """Investment asymmetry + trend direction = worth-your-time verdict."""
    if fp.total_messages < 50:
        fp.worth_your_time = "Too early to tell — need more conversation history."
        return

    if fp.fade_detected and fp.investment_asymmetry < -20:
        fp.worth_your_time = "Probably not right now. The effort is one-sided and getting worse."
    elif fp.fade_detected:
        fp.worth_your_time = "Watch carefully. Multiple signals are declining."
    elif fp.investment_asymmetry < -40:
        fp.worth_your_time = "You're doing most of the work. Either recalibrate or step back and see if they step up."
    elif fp.investment_asymmetry > 40:
        fp.worth_your_time = "They're clearly invested. Match their energy if you're interested."
    elif abs(fp.investment_asymmetry) < 15:
        fp.worth_your_time = "Balanced and healthy. Both people are showing up."
    else:
        fp.worth_your_time = "Slight tilt but nothing alarming. Keep building."
