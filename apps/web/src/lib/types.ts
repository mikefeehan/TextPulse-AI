export type RelationshipType =
  | "date"
  | "friend"
  | "coworker"
  | "family"
  | "other";

export interface User {
  id: string;
  email: string;
  created_at: string;
  last_login_at: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface MetricExample {
  message_id: string;
  text: string;
  timestamp: string;
  note: string;
}

export interface KeyTakeaway {
  title: string;
  detail: string;
}

export interface ProfileSection {
  summary: string;
  examples: MetricExample[];
  metrics: Record<string, unknown>;
}

export interface DatingSection {
  interest_level_score: number;
  attraction_indicators: string[];
  distance_indicators: string[];
  interest_trajectory: string;
  what_they_seem_to_want: string;
  strategic_insights: string[];
  the_play: string;
}

export interface RedGreenFlag {
  label: string;
  severity: string;
  detail: string;
  examples: MetricExample[];
}

export interface TimelineShift {
  title: string;
  summary: string;
  timestamp: string | null;
}

export interface ReceiptCard {
  headline: string;
  one_line_roast: string;
  interest_level: number;
  top_traits: string[];
  red_flags: string[];
  green_flags: string[];
  catchphrases: string[];
}

export interface PlaybookDocument {
  communication_cheat_sheet: string[];
  emotional_playbook: string[];
  date_planning_intelligence: string[];
  conflict_resolution_guide: string[];
  advance_moves: string[];
  two_week_strategy: string[];
  gift_ideas: string[];
}

export interface ViralSignals {
  ghost_probability: number;
  toxicity_score: number;
  heat_index: number;
  receipt: ReceiptCard;
  playbook: PlaybookDocument;
}

export interface ContactProfile {
  key_takeaways: KeyTakeaway[];
  personality_overview: ProfileSection;
  communication_style: ProfileSection;
  emotional_landscape: ProfileSection;
  values_and_interests: ProfileSection;
  humor_profile: ProfileSection;
  relationship_dynamics: ProfileSection;
  dating_mode?: DatingSection | null;
  red_flags: RedGreenFlag[];
  green_flags: RedGreenFlag[];
  timeline_and_evolution: TimelineShift[];
  viral_signals: ViralSignals;
  freshness: {
    latest_message_at?: string | null;
    latest_import_at?: string | null;
    latest_message_age_days?: number | null;
    stale: boolean;
  };
}

export interface ImportSummary {
  id: string;
  source_platform: string;
  file_name: string;
  message_count: number;
  status: string;
  error_details?: string | null;
  imported_at: string;
  date_range: {
    start: string | null;
    end: string | null;
  };
}

export type ImportStatusResponse = ImportSummary;

export interface ParsedMessagePreview {
  canonical_id: string;
  sender: string;
  text: string;
  timestamp: string;
  message_type: string;
}

export interface ImportContactOption {
  identifier: string;
  label: string;
  total_messages: number;
  sent_messages: number;
  received_messages: number;
  latest_message_at: string | null;
}

export interface ImportPreviewResponse {
  preview_id: string | null;
  file_name: string;
  source_platform: string;
  message_count: number;
  date_range: {
    start: string | null;
    end: string | null;
  };
  previews: ParsedMessagePreview[];
  stats: Record<string, string | number>;
  selection_required: boolean;
  contact_options: ImportContactOption[];
}

export interface ImportUploadResponse {
  import_id: string;
  status: string;
  message_count: number;
  profile_refreshed: boolean;
  queued: boolean;
  preview?: ImportPreviewResponse | null;
  import_record: ImportStatusResponse | null;
}

export interface ContactSummary {
  id: string;
  name: string;
  relationship_type: RelationshipType;
  is_dating_mode: boolean;
  photo_url: string | null;
  profile_generated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContactListItem extends ContactSummary {
  latest_message_at: string | null;
  message_count: number;
  import_count: number;
  top_takeaway: string | null;
}

export interface AnalyticsSeriesPoint {
  label: string;
  user_count: number;
  contact_count: number;
}

export interface HeatMapCell {
  day: string;
  hour: number;
  count: number;
}

export interface TopicStat {
  label: string;
  count: number;
}

export interface EmojiStat {
  emoji: string;
  count: number;
}

export interface AnalyticsPayload {
  message_volume: AnalyticsSeriesPoint[];
  response_time_distribution: AnalyticsSeriesPoint[];
  initiation_ratio: AnalyticsSeriesPoint[];
  message_length_trends: AnalyticsSeriesPoint[];
  sentiment_trend: AnalyticsSeriesPoint[];
  activity_heatmap: HeatMapCell[];
  top_topics: TopicStat[];
  emoji_usage: EmojiStat[];
  stats: Record<string, string | number | boolean | null>;
}

export interface ContactDetail extends ContactSummary {
  profile: ContactProfile | null;
  analytics: AnalyticsPayload;
  imports: ImportSummary[];
  recent_messages: MetricExample[];
}

export interface QAMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface QASession {
  id: string;
  created_at: string;
  messages: QAMessage[];
}

export interface QAReply {
  session_id: string;
  answer: string;
  supporting_examples: string[];
  cited_messages: string[];
}

export interface ReplyOption {
  label: string;
  tone: string;
  message: string;
  what_it_signals: string;
  likely_reaction: string;
}

export interface ReplyCoachResponse {
  id: string;
  incoming_message: string;
  subtext_analysis: string;
  reply_options: ReplyOption[];
  danger_zones: string[];
  timing_recommendation: string;
  escalation_guidance: string;
  created_at: string;
}

export interface VaultCategoryRead {
  id: string;
  name: string;
  emoji: string;
  description: string;
  count: number;
  is_default: boolean;
  is_active: boolean;
}

export interface VaultMessageCard {
  message_id: string;
  text: string;
  timestamp: string;
  reasoning: string;
  confidence: number;
  context_before: string[];
  context_after: string[];
}

export interface VaultCategoryDetail {
  category: VaultCategoryRead;
  stats: Record<string, string | number>;
  messages: VaultMessageCard[];
}

export interface ImportInstruction {
  platform: string;
  title: string;
  steps: string[];
  notes: string[];
  accepted_extensions: string[];
}

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}
