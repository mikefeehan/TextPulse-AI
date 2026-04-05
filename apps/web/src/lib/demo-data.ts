import {
  AnalyticsPayload,
  ContactDetail,
  ContactListItem,
  ImportInstruction,
  QASession,
  ReplyCoachResponse,
  User,
  VaultCategoryDetail,
  VaultCategoryRead,
} from "@/lib/types";

const now = "2026-03-19T00:18:00.000Z";

export const demoUser: User = {
  id: "demo-user",
  email: "demo@textpulse.ai",
  created_at: "2026-03-18T18:00:00.000Z",
  last_login_at: now,
};

function analytics(): AnalyticsPayload {
  return {
    message_volume: [
      { label: "2025-10", user_count: 28, contact_count: 31 },
      { label: "2025-11", user_count: 42, contact_count: 39 },
      { label: "2025-12", user_count: 57, contact_count: 61 },
      { label: "2026-01", user_count: 63, contact_count: 58 },
      { label: "2026-02", user_count: 49, contact_count: 46 },
      { label: "2026-03", user_count: 21, contact_count: 18 },
    ],
    response_time_distribution: [
      { label: "<5m", user_count: 18, contact_count: 12 },
      { label: "5-30m", user_count: 37, contact_count: 33 },
      { label: "30-120m", user_count: 26, contact_count: 21 },
      { label: "2-8h", user_count: 14, contact_count: 19 },
      { label: "8h+", user_count: 6, contact_count: 9 },
    ],
    initiation_ratio: [
      { label: "2025-12", user_count: 8, contact_count: 6 },
      { label: "2026-01", user_count: 7, contact_count: 8 },
      { label: "2026-02", user_count: 6, contact_count: 5 },
      { label: "2026-03", user_count: 3, contact_count: 2 },
    ],
    message_length_trends: [
      { label: "2025-12", user_count: 78, contact_count: 93 },
      { label: "2026-01", user_count: 88, contact_count: 101 },
      { label: "2026-02", user_count: 74, contact_count: 79 },
      { label: "2026-03", user_count: 67, contact_count: 63 },
    ],
    sentiment_trend: [
      { label: "2025-12", user_count: 0.32, contact_count: 0.38 },
      { label: "2026-01", user_count: 0.42, contact_count: 0.35 },
      { label: "2026-02", user_count: 0.19, contact_count: 0.12 },
      { label: "2026-03", user_count: 0.27, contact_count: 0.22 },
    ],
    activity_heatmap: [
      { day: "Mon", hour: 10, count: 3 },
      { day: "Tue", hour: 18, count: 9 },
      { day: "Wed", hour: 20, count: 12 },
      { day: "Thu", hour: 21, count: 11 },
      { day: "Fri", hour: 19, count: 14 },
      { day: "Sat", hour: 13, count: 8 },
      { day: "Sun", hour: 18, count: 6 },
    ],
    top_topics: [
      { label: "travel", count: 16 },
      { label: "plans", count: 13 },
      { label: "work", count: 12 },
      { label: "music", count: 9 },
      { label: "family", count: 7 },
      { label: "weekend", count: 7 },
    ],
    emoji_usage: [
      { emoji: "😂", count: 22 },
      { emoji: "❤️", count: 16 },
      { emoji: "😭", count: 9 },
      { emoji: "✨", count: 8 },
      { emoji: "👀", count: 7 },
    ],
    stats: {
      total_messages: 513,
      contact_messages: 253,
      user_messages: 260,
      avg_contact_response_seconds: 6234,
      avg_user_response_seconds: 5042,
      latest_message_at: "2026-03-18T23:30:00.000Z",
    },
  };
}

function profile(name: string, datingMode = false): ContactDetail["profile"] {
  return {
    key_takeaways: [
      { title: "High-Leverage Topic", detail: "They light up around travel, music, and concrete plans. Abstract relationship talk lands better after momentum is already warm." },
      { title: "Pacing Read", detail: "They are responsive when interested but visibly slower when bandwidth or certainty drops. Their timing is a stronger signal than their wording." },
      { title: "Communication Sweet Spot", detail: "They respond best to confident, low-pressure messages that are specific and easy to answer." },
      { title: "Guardrail", detail: "Avoid emotional stacking. When the thread gets tense, shorter and cleaner messages work much better than persuasive walls of text." },
      { title: "Current Temperature", detail: datingMode ? "Interest looks real but not fully locked in. The best move is to keep things clear, calm, and forward." : "The relationship has solid trust with occasional pacing mismatches during stressful stretches." },
    ],
    personality_overview: {
      summary: `${name} reads as socially fluid, curious, and emotionally selective. They show warmth once they feel safe, but they protect their bandwidth when life gets crowded.`,
      examples: [
        { message_id: "m1", text: "You'd love this place in Lisbon, it's exactly your vibe.", timestamp: "2026-02-11T19:10:00.000Z", note: "Curiosity plus future projection." },
        { message_id: "m2", text: "I overthink when I'm tired, so if I get quiet that's usually why.", timestamp: "2026-02-21T22:03:00.000Z", note: "Self-awareness with guarded vulnerability." },
      ],
      metrics: {
        big_five: {
          openness: 71,
          conscientiousness: 58,
          extraversion: 64,
          agreeableness: 61,
          neuroticism: 49,
        },
        mbti_estimate: "ENFJ",
        enneagram_estimate: "2w3",
      },
    },
    communication_style: {
      summary: "Their texts are energetic when momentum is good and noticeably shorter when they are overloaded. They prefer natural rhythm over constant check-ins.",
      examples: [
        { message_id: "m3", text: "Thursday works. 7pm and we'll keep it easy.", timestamp: "2026-03-02T18:44:00.000Z", note: "Best form of engagement: warm plus decisive." },
        { message_id: "m4", text: "I can't tonight but I'm not disappearing lol.", timestamp: "2026-03-05T21:18:00.000Z", note: "Humor softens boundaries." },
      ],
      metrics: {
        avg_contact_message_length: 92,
        avg_user_message_length: 84,
        avg_contact_response_seconds: 6234,
        avg_user_response_seconds: 5042,
        top_topics: ["travel", "plans", "work", "music"],
      },
    },
    emotional_landscape: {
      summary: "They can be open, but only when the environment feels emotionally efficient. Stress shows up as slower replies, narrower wording, and postponing hard topics.",
      examples: [
        { message_id: "m5", text: "Today kind of drained me. I want to talk, just not like this minute.", timestamp: "2026-02-25T20:31:00.000Z", note: "Classic low-capacity but not low-interest signal." },
      ],
      metrics: {
        trigger_topics: ["unclear plans", "pressure", "mixed signals"],
        stress_signals: ["Shorter replies", "Explaining they are busy", "Deferring emotional processing"],
        soothers: ["Direct reassurance", "Specific next steps", "Respecting space once stated"],
      },
    },
    values_and_interests: {
      summary: "The history suggests they prioritize freedom, interesting experiences, and feeling emotionally understood without being cornered.",
      examples: [
        { message_id: "m6", text: "A perfect night is good food, good music, and not being rushed.", timestamp: "2026-01-09T23:12:00.000Z", note: "Values statement hidden inside casual talk." },
      ],
      metrics: {
        core_values: ["Adventure", "Emotional safety", "Career progress"],
        passions: ["travel", "music", "good food", "creative work"],
        pet_peeves: ["Vague planning", "Needless pressure"],
      },
    },
    humor_profile: {
      summary: "Playful, lightly sarcastic, and most alive when the banter feels co-created rather than performative.",
      examples: [
        { message_id: "m7", text: "Your calendar discipline is both attractive and slightly terrifying 😂", timestamp: "2026-02-17T16:41:00.000Z", note: "Affection wrapped in teasing." },
      ],
      metrics: {
        humor_type: "playful and lightly dry",
        inside_jokes: ["airport energy", "calendar menace", "sad desk lunch"],
        laugh_ratio: 0.18,
      },
    },
    relationship_dynamics: {
      summary: datingMode
        ? "There is enough reciprocity to keep leaning in, but not enough consistency to over-invest emotionally without clearer momentum."
        : "The relationship is supportive and collaborative, with friction mostly happening when one side is overloaded.",
      examples: [
        { message_id: "m8", text: "I'm still in, I just need cleaner planning from both of us.", timestamp: "2026-03-03T11:22:00.000Z", note: "Boundary plus repair." },
      ],
      metrics: {
        power_dynamics: "balanced with slight user over-initiation",
        investment_level: datingMode ? 7 : 8,
        reciprocity_gap: 7,
        trust_trajectory: "warming",
      },
    },
    dating_mode: datingMode
      ? {
          interest_level_score: 7,
          attraction_indicators: [
            "They initiate playful teasing when the mood is good.",
            "They move toward concrete plans when timing feels easy.",
          ],
          distance_indicators: [
            "They soften uncertainty with humor instead of direct rejection.",
            "Their response time widens when pressure rises.",
          ],
          interest_trajectory: "rising with occasional caution spikes",
          what_they_seem_to_want: "A connection that feels exciting but emotionally low-chaos.",
          strategic_insights: [
            "Lead with one plan, not a cloud of options.",
            "Stay confident without making them manage your reassurance.",
            "Reward momentum instead of interrogating hesitation.",
          ],
          the_play: "Pull back slightly on extra check-ins, re-enter with one clean plan, and let their follow-through answer the question.",
        }
      : null,
    red_flags: [
      {
        label: "Excuses",
        severity: "high",
        detail: "There are moments where they postpone without immediately replacing the plan.",
        examples: [
          { message_id: "m9", text: "Something came up today. Rain check?", timestamp: "2026-02-28T17:09:00.000Z", note: "Soft exit without replacement plan." },
        ],
      },
    ],
    green_flags: [
      {
        label: "Green Flags",
        severity: "positive",
        detail: "They do show accountability when they know they created friction.",
        examples: [
          { message_id: "m10", text: "You're right, I made that harder than it needed to be. That's on me.", timestamp: "2026-03-01T09:41:00.000Z", note: "Repair with ownership." },
        ],
      },
    ],
    timeline_and_evolution: [
      { title: "Warmer Planning Phase", summary: "January through early February carried the strongest plan-making momentum.", timestamp: "2026-02-04T20:00:00.000Z" },
      { title: "Stress Compression", summary: "Late February introduced more scheduling strain and slower replies.", timestamp: "2026-02-24T20:00:00.000Z" },
      { title: "Current State", summary: "The connection still has warmth, but clarity now matters more than volume.", timestamp: "2026-03-18T23:30:00.000Z" },
    ],
    viral_signals: {
      ghost_probability: 36,
      toxicity_score: 24,
      heat_index: 71,
      receipt: {
        headline: "Relationship Receipt",
        one_line_roast: "Emotionally available enough to flirt, but allergic to messy logistics.",
        interest_level: datingMode ? 7 : 8,
        top_traits: ["Openness", "Extraversion", "Agreeableness"],
        red_flags: ["Excuses"],
        green_flags: ["Green Flags"],
        catchphrases: ["travel", "plans", "music", "weekend"],
      },
      playbook: {
        communication_cheat_sheet: [
          "Send one clear ask at a time.",
          "Mirror their pacing once the conversation is live.",
          "Keep serious topics tighter and calmer.",
        ],
        emotional_playbook: [
          "If they are stressed, remove pressure before asking for clarity.",
          "Specific reassurance works better than broad emotional speeches.",
        ],
        date_planning_intelligence: [
          "Music, food, and novelty-rich plans work better than generic hangouts.",
          "Thursday and Friday evenings are strong windows.",
        ],
        conflict_resolution_guide: [
          "Lead with impact, not accusation.",
          "Give them one path to repair instead of several demands.",
        ],
        advance_moves: [
          "Escalate only after a warm run of replies.",
          "Do not over-text in the gap between setting and confirming a plan.",
        ],
        two_week_strategy: [
          "Week 1: rebuild easy momentum around one fun topic.",
          "Week 2: convert that momentum into a specific plan or a clear conversation.",
        ],
        gift_ideas: ["Tickets, playlists, travel-adjacent surprises, or anything thoughtful but unfussy."],
      },
    },
    freshness: {
      latest_message_at: "2026-03-18T23:30:00.000Z",
      latest_import_at: "2026-03-18T23:45:00.000Z",
      latest_message_age_days: 0,
      stale: false,
    },
  };
}

function contactDetail(id: string, name: string, relationship: ContactListItem["relationship_type"], datingMode: boolean): ContactDetail {
  return {
    id,
    name,
    relationship_type: relationship,
    is_dating_mode: datingMode,
    photo_url: null,
    profile_generated_at: now,
    created_at: "2025-10-01T14:00:00.000Z",
    updated_at: now,
    profile: profile(name, datingMode),
    analytics: analytics(),
    imports: [
      {
        id: `${id}-import-1`,
        source_platform: "whatsapp",
        file_name: "whatsapp-export.txt",
        message_count: 341,
        status: "completed",
        imported_at: "2026-03-18T23:45:00.000Z",
        date_range: {
          start: "2025-10-01T14:00:00.000Z",
          end: "2026-03-18T23:30:00.000Z",
        },
      },
      {
        id: `${id}-import-2`,
        source_platform: "screenshot",
        file_name: "march-checkin.png",
        message_count: 12,
        status: "completed",
        imported_at: "2026-03-18T23:48:00.000Z",
        date_range: {
          start: "2026-03-18T18:11:00.000Z",
          end: "2026-03-18T23:30:00.000Z",
        },
      },
    ],
    recent_messages: [
      { message_id: "m11", text: "Thursday works. 7 and we keep it easy?", timestamp: "2026-03-18T18:11:00.000Z", note: "contact" },
      { message_id: "m12", text: "Perfect. I'll send you the spot.", timestamp: "2026-03-18T18:13:00.000Z", note: "user" },
      { message_id: "m13", text: "You're aggressively organized and I respect it 😂", timestamp: "2026-03-18T18:15:00.000Z", note: "contact" },
      { message_id: "m14", text: "I choose to hear only 'respect it'.", timestamp: "2026-03-18T18:17:00.000Z", note: "user" },
    ],
  };
}

export const demoContacts: ContactListItem[] = [
  {
    id: "c-ava",
    name: "Ava",
    relationship_type: "date",
    is_dating_mode: true,
    photo_url: null,
    profile_generated_at: now,
    created_at: "2025-10-01T14:00:00.000Z",
    updated_at: now,
    latest_message_at: "2026-03-18T23:30:00.000Z",
    message_count: 513,
    import_count: 2,
    top_takeaway: "Interest is real, but timing and clarity matter more than intensity right now.",
  },
  {
    id: "c-daniel",
    name: "Daniel",
    relationship_type: "coworker",
    is_dating_mode: false,
    photo_url: null,
    profile_generated_at: now,
    created_at: "2025-11-01T08:00:00.000Z",
    updated_at: now,
    latest_message_at: "2026-03-17T16:40:00.000Z",
    message_count: 284,
    import_count: 1,
    top_takeaway: "Strong collaborator, fast on logistics, slower when conflict needs emotional nuance.",
  },
];

export const demoContactDetails: Record<string, ContactDetail> = {
  "c-ava": contactDetail("c-ava", "Ava", "date", true),
  "c-daniel": contactDetail("c-daniel", "Daniel", "coworker", false),
};

export const demoVaultCategories: VaultCategoryRead[] = [
  { id: "cat-flirty", name: "Flirty / Sexual", emoji: "🔥", description: "Flirtation, chemistry, and sexual tension.", count: 18, is_default: true, is_active: true },
  { id: "cat-green", name: "Green Flags", emoji: "🟢", description: "Repair, consistency, and emotional maturity.", count: 9, is_default: true, is_active: true },
  { id: "cat-plans", name: "Plans & Promises", emoji: "📅", description: "Plans, commitments, and follow-through.", count: 14, is_default: true, is_active: true },
  { id: "cat-excuses", name: "Excuses", emoji: "🙄", description: "Soft exits, postponements, or vague availability.", count: 6, is_default: true, is_active: true },
];

export const demoVaultDetails: Record<string, VaultCategoryDetail> = {
  "cat-flirty": {
    category: demoVaultCategories[0],
    stats: {
      total_messages: 18,
      first_occurrence: "2025-11-11T22:14:00.000Z",
      latest_occurrence: "2026-03-18T18:15:00.000Z",
      share_of_conversation: 3.5,
    },
    messages: [
      {
        message_id: "m15",
        text: "You're aggressively organized and I respect it 😂",
        timestamp: "2026-03-18T18:15:00.000Z",
        reasoning: "Teasing paired with praise and warmth.",
        confidence: 0.88,
        context_before: ["Thursday works. 7 and we keep it easy?"],
        context_after: ["I choose to hear only 'respect it'."],
      },
      {
        message_id: "m16",
        text: "If you keep talking like that I might actually miss you.",
        timestamp: "2026-02-14T22:01:00.000Z",
        reasoning: "Direct flirtation with vulnerability.",
        confidence: 0.91,
        context_before: ["So are we doing this or just being cute about it?"],
        context_after: ["Bold accusation but fair."],
      },
    ],
  },
  "cat-green": {
    category: demoVaultCategories[1],
    stats: {
      total_messages: 9,
      first_occurrence: "2025-12-07T09:12:00.000Z",
      latest_occurrence: "2026-03-01T09:41:00.000Z",
      share_of_conversation: 1.8,
    },
    messages: [
      {
        message_id: "m10",
        text: "You're right, I made that harder than it needed to be. That's on me.",
        timestamp: "2026-03-01T09:41:00.000Z",
        reasoning: "Direct ownership without defensiveness.",
        confidence: 0.94,
        context_before: ["I think we crossed wires yesterday."],
        context_after: ["Thank you for saying that."],
      },
    ],
  },
};

export const demoInstructions: ImportInstruction[] = [
  {
    platform: "imessage",
    title: "Import iMessage history",
    steps: [
      "Pull the chat.db file from an Apple backup or macOS Messages archive.",
      "Upload the database and choose the contact thread.",
      "Review the parsed preview before committing the import.",
    ],
    notes: ["Supports reactions, timestamps, and long-history merging."],
    accepted_extensions: [".db", ".sqlite"],
  },
  {
    platform: "whatsapp",
    title: "Import WhatsApp export",
    steps: [
      "Use WhatsApp Export Chat from the conversation menu.",
      "Choose no media for faster parsing.",
      "Upload the exported .txt file directly.",
    ],
    notes: ["The parser supports the two most common export line formats."],
    accepted_extensions: [".txt", ".zip"],
  },
  {
    platform: "screenshot",
    title: "Import screenshots",
    steps: [
      "Drop one or multiple screenshots into the import tray.",
      "We run OCR and sequence the conversation chronologically.",
      "Confirm the parsed preview before merging it into the timeline.",
    ],
    notes: ["Best for fresh reply-coach context or quick missing-history patches."],
    accepted_extensions: [".png", ".jpg", ".jpeg"],
  },
];

export const demoQaSession: QASession = {
  id: "qa-1",
  created_at: now,
  messages: [
    {
      id: "qa-m1",
      role: "user",
      content: "Why did they go quiet after we made plans?",
      created_at: now,
    },
    {
      id: "qa-m2",
      role: "assistant",
      content: "The pattern in this history is less about loss of interest and more about capacity compression. When plans get real, they tend to slow down if the rest of life is crowded. The better read is whether they circle back with clarity afterward.",
      created_at: now,
    },
  ],
};

export const demoReplyCoach: ReplyCoachResponse = {
  id: "coach-1",
  incoming_message: "I'm slammed today but I still want to see you this week.",
  subtext_analysis: "This reads as genuine interest with low bandwidth, not a soft rejection. The important signal is that they preserved the plan horizon instead of disappearing.",
  reply_options: [
    {
      label: "Safe",
      tone: "calm",
      message: "No stress, handle your day. We can lock something in when you're breathing again.",
      what_it_signals: "You are low-pressure and emotionally steady.",
      likely_reaction: "Keeps safety high and makes it easier for them to re-engage.",
    },
    {
      label: "Warm",
      tone: "empathetic",
      message: "Totally get it. I still want to see you too, so when your brain comes back online let's pick something simple.",
      what_it_signals: "You noticed the context without making them manage your feelings.",
      likely_reaction: "Likely to create a warmer follow-up once they have bandwidth.",
    },
    {
      label: "Forward",
      tone: "direct",
      message: "Done. Let's make it easy then: Thursday night or Saturday afternoon?",
      what_it_signals: "Confident and clean momentum.",
      likely_reaction: "Best when they respond well to clear options and already sound invested.",
    },
  ],
  danger_zones: [
    "Do not punish the delay if they are still signaling intent.",
    "Avoid sending a heavy reassurance-seeking message while they are low-capacity.",
  ],
  timing_recommendation: "Reply same day while the thread is warm, but keep it concise.",
  escalation_guidance: "Move forward a little, but with one simple next step rather than emotional intensity.",
  created_at: now,
};
