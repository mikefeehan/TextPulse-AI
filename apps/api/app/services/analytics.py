from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from app.models import Message, SenderType
from app.schemas.contacts import AnalyticsPayload, AnalyticsSeriesPoint, EmojiStat, HeatMapCell, TopicStat
from app.services.text_utils import count_emojis, keyword_counts, month_bucket

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
RESPONSE_BUCKETS = [
    ("<5m", 0, 300),
    ("5-30m", 300, 1_800),
    ("30-120m", 1_800, 7_200),
    ("2-8h", 7_200, 28_800),
    ("8h+", 28_800, float("inf")),
]


def build_contact_analytics(messages: list[Message]) -> AnalyticsPayload:
    if not messages:
        return AnalyticsPayload(
            message_volume=[],
            response_time_distribution=[],
            initiation_ratio=[],
            message_length_trends=[],
            sentiment_trend=[],
            activity_heatmap=[],
            top_topics=[],
            emoji_usage=[],
            stats={},
        )

    monthly_volume: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {
            "user_volume": [],
            "contact_volume": [],
            "user_lengths": [],
            "contact_lengths": [],
            "user_sentiment": [],
            "contact_sentiment": [],
        }
    )
    initiations: dict[str, dict[str, int]] = defaultdict(lambda: {"user": 0, "contact": 0})
    response_buckets: dict[str, dict[str, int]] = {
        label: {"user": 0, "contact": 0} for label, _, _ in RESPONSE_BUCKETS
    }
    heatmap: dict[tuple[str, int], int] = defaultdict(int)
    emoji_counter: Counter[str] = Counter()
    topic_counter: Counter[str] = Counter()

    last_session_id = None
    for message in sorted(messages, key=lambda row: row.timestamp):
        month = month_bucket(message.timestamp)
        sender_key = "user" if message.sender == SenderType.USER else "contact"
        monthly_volume[month][f"{sender_key}_volume"].append(1.0)
        monthly_volume[month][f"{sender_key}_lengths"].append(float(len(message.message_text)))
        if message.sentiment_score is not None:
            monthly_volume[month][f"{sender_key}_sentiment"].append(message.sentiment_score)

        if message.session_id != last_session_id:
            initiations[month][sender_key] += 1
            last_session_id = message.session_id

        if message.response_time_seconds is not None:
            for label, lower, upper in RESPONSE_BUCKETS:
                if lower <= message.response_time_seconds < upper:
                    response_buckets[label][sender_key] += 1
                    break

        day_name = DAY_NAMES[message.timestamp.weekday()]
        heatmap[(day_name, message.timestamp.hour)] += 1
        emoji_counter.update(count_emojis(message.message_text))
        topic_counter.update(keyword_counts([message.message_text]))

    message_volume = [
        AnalyticsSeriesPoint(
            label=month,
            user_count=int(sum(values["user_volume"])),
            contact_count=int(sum(values["contact_volume"])),
        )
        for month, values in monthly_volume.items()
    ]
    message_length_trends = [
        AnalyticsSeriesPoint(
            label=month,
            user_count=round(mean(values["user_lengths"]) if values["user_lengths"] else 0, 1),
            contact_count=round(mean(values["contact_lengths"]) if values["contact_lengths"] else 0, 1),
        )
        for month, values in monthly_volume.items()
    ]
    sentiment_trend = [
        AnalyticsSeriesPoint(
            label=month,
            user_count=round(mean(values["user_sentiment"]) if values["user_sentiment"] else 0, 2),
            contact_count=round(mean(values["contact_sentiment"]) if values["contact_sentiment"] else 0, 2),
        )
        for month, values in monthly_volume.items()
    ]
    initiation_ratio = [
        AnalyticsSeriesPoint(
            label=month,
            user_count=values["user"],
            contact_count=values["contact"],
        )
        for month, values in initiations.items()
    ]
    response_time_distribution = [
        AnalyticsSeriesPoint(
            label=label,
            user_count=values["user"],
            contact_count=values["contact"],
        )
        for label, values in response_buckets.items()
    ]
    activity_heatmap = [
        HeatMapCell(day=day, hour=hour, count=count)
        for (day, hour), count in sorted(heatmap.items(), key=lambda row: (DAY_NAMES.index(row[0][0]), row[0][1]))
    ]
    top_topics = [TopicStat(label=label, count=count) for label, count in topic_counter.most_common(12)]
    emoji_usage = [EmojiStat(emoji=emoji, count=count) for emoji, count in emoji_counter.most_common(8)]

    user_messages = [message for message in messages if message.sender == SenderType.USER]
    contact_messages = [message for message in messages if message.sender == SenderType.CONTACT]
    avg_contact_response = _avg_response_time(contact_messages)
    avg_user_response = _avg_response_time(user_messages)

    stats: dict[str, Any] = {
        "total_messages": len(messages),
        "contact_messages": len(contact_messages),
        "user_messages": len(user_messages),
        "avg_contact_response_seconds": avg_contact_response,
        "avg_user_response_seconds": avg_user_response,
        "latest_message_at": messages[-1].timestamp.isoformat(),
    }

    return AnalyticsPayload(
        message_volume=message_volume,
        response_time_distribution=response_time_distribution,
        initiation_ratio=initiation_ratio,
        message_length_trends=message_length_trends,
        sentiment_trend=sentiment_trend,
        activity_heatmap=activity_heatmap,
        top_topics=top_topics,
        emoji_usage=emoji_usage,
        stats=stats,
    )


def _avg_response_time(messages: list[Message]) -> float:
    responses = [message.response_time_seconds for message in messages if message.response_time_seconds is not None]
    return round(mean(responses), 2) if responses else 0.0
