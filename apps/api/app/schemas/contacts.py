from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.entities import RelationshipType
from app.schemas.common import AIQualityMode, DateRangeSummary, MetricExample, ORMModel


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    relationship_type: RelationshipType
    is_dating_mode: bool = False
    photo_url: str | None = None


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    relationship_type: RelationshipType | None = None
    is_dating_mode: bool | None = None
    photo_url: str | None = None


class AnalysisRegenerateRequest(BaseModel):
    quality_mode: AIQualityMode | None = None


class KeyTakeaway(BaseModel):
    title: str
    detail: str


class TraitScore(BaseModel):
    score: int
    confidence: str
    reasoning: str


class ProfileSection(BaseModel):
    summary: str
    examples: list[MetricExample] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class DatingSection(BaseModel):
    interest_level_score: int
    attraction_indicators: list[str]
    distance_indicators: list[str]
    interest_trajectory: str
    what_they_seem_to_want: str
    strategic_insights: list[str]
    the_play: str


class RedGreenFlag(BaseModel):
    label: str
    severity: str
    detail: str
    examples: list[MetricExample] = Field(default_factory=list)


class TimelineShift(BaseModel):
    title: str
    summary: str
    timestamp: datetime | None = None


class ReceiptCard(BaseModel):
    headline: str
    one_line_roast: str
    interest_level: int
    top_traits: list[str]
    red_flags: list[str]
    green_flags: list[str]
    catchphrases: list[str]


class PlaybookDocument(BaseModel):
    communication_cheat_sheet: list[str]
    emotional_playbook: list[str]
    date_planning_intelligence: list[str]
    conflict_resolution_guide: list[str]
    advance_moves: list[str]
    two_week_strategy: list[str]
    gift_ideas: list[str]


class ViralSignals(BaseModel):
    ghost_probability: int
    toxicity_score: int
    heat_index: int
    receipt: ReceiptCard
    playbook: PlaybookDocument


class AIStrategy(BaseModel):
    provider: str
    quality_mode: AIQualityMode | None = None
    profile_model: str | None = None
    live_model: str | None = None
    budget_profile_usd: float | None = None
    budget_live_usd: float | None = None
    notes: list[str] = Field(default_factory=list)


class ContactProfile(BaseModel):
    key_takeaways: list[KeyTakeaway]
    personality_overview: ProfileSection
    communication_style: ProfileSection
    emotional_landscape: ProfileSection
    values_and_interests: ProfileSection
    humor_profile: ProfileSection
    relationship_dynamics: ProfileSection
    dating_mode: DatingSection | None = None
    red_flags: list[RedGreenFlag]
    green_flags: list[RedGreenFlag]
    timeline_and_evolution: list[TimelineShift]
    viral_signals: ViralSignals
    freshness: dict[str, Any]
    ai_strategy: AIStrategy | None = None


class ImportSummary(BaseModel):
    id: str
    source_platform: str
    file_name: str
    message_count: int
    status: str
    error_details: str | None = None
    imported_at: datetime
    date_range: DateRangeSummary


class ContactSummary(ORMModel):
    id: str
    name: str
    relationship_type: RelationshipType
    is_dating_mode: bool
    photo_url: str | None
    profile_generated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ContactListItem(ContactSummary):
    latest_message_at: datetime | None = None
    message_count: int = 0
    import_count: int = 0
    top_takeaway: str | None = None


class AnalyticsSeriesPoint(BaseModel):
    label: str
    user_count: int | float
    contact_count: int | float


class HeatMapCell(BaseModel):
    day: str
    hour: int
    count: int


class TopicStat(BaseModel):
    label: str
    count: int


class EmojiStat(BaseModel):
    emoji: str
    count: int


class AnalyticsPayload(BaseModel):
    message_volume: list[AnalyticsSeriesPoint]
    response_time_distribution: list[AnalyticsSeriesPoint]
    initiation_ratio: list[AnalyticsSeriesPoint]
    message_length_trends: list[AnalyticsSeriesPoint]
    sentiment_trend: list[AnalyticsSeriesPoint]
    activity_heatmap: list[HeatMapCell]
    top_topics: list[TopicStat]
    emoji_usage: list[EmojiStat]
    stats: dict[str, Any]


class ContactDetail(ContactSummary):
    profile: ContactProfile | None = None
    analytics: AnalyticsPayload
    imports: list[ImportSummary]
    recent_messages: list[MetricExample]
