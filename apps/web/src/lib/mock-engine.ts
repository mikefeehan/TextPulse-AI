import {
  ContactDetail,
  QAMessage,
  QASession,
  QAReply,
  ReplyCoachResponse,
  ReplyOption,
} from "@/lib/types";

function timestamp() {
  return new Date().toISOString();
}

export function createDemoQaReply(
  contact: ContactDetail,
  question: string,
  session: QASession,
): QAReply {
  const lower = question.toLowerCase();
  const topTakeaway =
    contact.profile?.key_takeaways[0]?.detail ??
    "The cleanest read comes from pacing, topic choice, and follow-through.";

  let answer = topTakeaway;
  if (lower.includes("interested") || lower.includes("like me")) {
    answer =
      "The strongest sign of interest here is not a single flirty line, it is their pattern of coming back into the conversation and keeping plans alive. The risk is inconsistency under stress, not indifference by default.";
  } else if (lower.includes("apologize") || lower.includes("sorry")) {
    answer =
      "Lead with one clear ownership statement, one impact statement, and one repair move. This person responds better to calm accountability than emotional overexplaining.";
  } else if (lower.includes("hang out") || lower.includes("weekend") || lower.includes("plan")) {
    answer =
      "Give them a narrow, easy-to-answer plan. They do better with specific options than vague momentum. Keep the tone relaxed and let the clarity do the work.";
  }

  answer +=
    " In this history, their best engagement tends to happen when the thread feels low-pressure but directionally clear.";

  return {
    session_id: session.id,
    answer,
    supporting_examples: contact.recent_messages.slice(0, 2).map((message) => message.text),
    cited_messages: contact.recent_messages.slice(0, 2).map((message) => message.message_id),
  };
}

export function appendDemoQaMessages(
  session: QASession,
  question: string,
  reply: QAReply,
): QASession {
  const nextMessages: QAMessage[] = [
    ...session.messages,
    {
      id: `user-${timestamp()}`,
      role: "user",
      content: question,
      created_at: timestamp(),
    },
    {
      id: `assistant-${timestamp()}`,
      role: "assistant",
      content: reply.answer,
      created_at: timestamp(),
    },
  ];
  return { ...session, messages: nextMessages };
}

export function createDemoReplyCoach(
  contact: ContactDetail,
  incomingMessage: string,
): ReplyCoachResponse {
  const lower = incomingMessage.toLowerCase();
  const isCold =
    lower.includes("busy") ||
    lower.includes("later") ||
    lower.includes("not sure") ||
    lower.includes("space");

  const options: ReplyOption[] = [
    {
      label: "Safe",
      tone: "calm",
      message: isCold
        ? "No problem, take care of your day. We can pick this back up when you have room."
        : "Love that. Keep me posted and let's make it easy.",
      what_it_signals: "Stable, low-pressure energy.",
      likely_reaction: "Makes it easier for them to keep engaging without defensiveness.",
    },
    {
      label: "Warm",
      tone: "empathetic",
      message: isCold
        ? "Totally get it. I still want to keep this moving, so circle back when you're less slammed."
        : "I'm into that. Feels like we're on the same page when we keep it this simple.",
      what_it_signals: "You noticed the emotional context without overdoing it.",
      likely_reaction: "Best for creating closeness while keeping the thread light.",
    },
    {
      label: "Forward",
      tone: "direct",
      message:
        "Let's keep this easy then. Thursday night or Saturday afternoon?",
      what_it_signals: "Clean confidence and momentum.",
      likely_reaction: "Strong when they respond well to specifics and real plans.",
    },
  ];

  return {
    id: `coach-${timestamp()}`,
    incoming_message: incomingMessage,
    subtext_analysis: `${
      contact.profile?.key_takeaways[1]?.detail ??
      "Their timing is often the clearest signal."
    } This latest message reads as ${isCold ? "interest with low bandwidth" : "positive engagement with room to move things forward"}.`,
    reply_options: options,
    danger_zones: [
      "Avoid over-texting when their bandwidth sounds low.",
      "Do not turn a scheduling hiccup into a relationship referendum.",
    ],
    timing_recommendation: isCold
      ? "Reply when you can be concise and calm. Thoughtful beats instant here."
      : "Reply while the thread is still warm, ideally the same day.",
    escalation_guidance: isCold
      ? "De-escalate slightly and keep it easy to answer."
      : "You can move things forward, but do it with one clean next step.",
    created_at: timestamp(),
  };
}
