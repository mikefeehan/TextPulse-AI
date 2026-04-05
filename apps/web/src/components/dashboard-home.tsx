"use client";

import Link from "next/link";
import { startTransition, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Brain,
  ChevronRight,
  FolderHeart,
  MessagesSquare,
  Shield,
  Upload,
  WandSparkles,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { EmptyState, InlineBadge, MetricCard, SectionCard } from "@/components/ui";
import { createContact, listContacts, listImportInstructions } from "@/lib/api";
import type { ContactListItem, ImportInstruction } from "@/lib/types";

export function DashboardHome() {
  const { booting, token, user, demoMode } = useAuth();
  const [contacts, setContacts] = useState<ContactListItem[]>([]);
  const [instructions, setInstructions] = useState<ImportInstruction[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [relationshipType, setRelationshipType] = useState<ContactListItem["relationship_type"]>("date");
  const [datingMode, setDatingMode] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    void Promise.all([listContacts(token), listImportInstructions()])
      .then(([nextContacts, nextInstructions]) => {
        startTransition(() => {
          setContacts(nextContacts);
          setInstructions(nextInstructions);
          setLoading(false);
        });
      })
      .catch(() => {
        setLoading(false);
      });
  }, [token]);

  const totalMessages = useMemo(
    () => contacts.reduce((sum, contact) => sum + contact.message_count, 0),
    [contacts],
  );
  const appleInstruction = instructions.find((instruction) => instruction.platform === "imessage");
  const secondaryInstructions = instructions.filter((instruction) => instruction.platform !== "imessage").slice(0, 3);

  async function handleCreateContact(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !name.trim()) {
      return;
    }
    setCreating(true);
    try {
      const created = await createContact(token, {
        name: name.trim(),
        relationship_type: relationshipType,
        is_dating_mode: datingMode,
      });
      setContacts((current) => [
        {
          ...created,
          latest_message_at: null,
          message_count: 0,
          import_count: 0,
          top_takeaway: "Fresh contact created. Import messages to generate the real profile.",
        },
        ...current,
      ]);
      setName("");
      toast.success(`Created ${created.name}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to create contact.");
    } finally {
      setCreating(false);
    }
  }

  if (booting) {
    return <BootScreen />;
  }

  if (!user) {
    return <MarketingExperience />;
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[1.4fr_0.9fr]">
        <div className="rounded-[2.5rem] border border-white/8 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.18),transparent_30%),linear-gradient(160deg,rgba(15,23,42,0.96),rgba(2,6,23,0.94))] p-7 shadow-[0_30px_120px_rgba(2,6,23,0.45)]">
          <div className="flex flex-wrap items-center gap-3">
            <InlineBadge tone="success">Private by design</InlineBadge>
            <InlineBadge tone={demoMode ? "warning" : "neutral"}>
              {demoMode ? "Running in demo-backed mode" : "Live backend connected"}
            </InlineBadge>
          </div>
          <div className="mt-6 max-w-3xl">
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-300/70">
              Predictive Relationship Intelligence
            </p>
            <h1 className="mt-3 max-w-2xl text-4xl font-semibold leading-tight tracking-tight text-white sm:text-5xl">
              Turn conversation history into predictive relationship intelligence.
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300">
              Import message history, identify the patterns that actually matter, and generate a living intelligence
              profile with evidence-backed insights, predictive signals, analytics, and reply coaching.
            </p>
          </div>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <MetricCard label="Active Contacts" value={contacts.length} hint="Each contact keeps its own profile, vault, and coaching context." />
            <MetricCard label="Imported Messages" value={totalMessages.toLocaleString()} hint="Cross-platform timelines ready for retrieval and analysis." accent="amber" />
            <MetricCard label="Profile Freshness" value={contacts[0]?.latest_message_at ? "Fresh" : "Needs import"} hint="The system nudges you when the latest history goes stale." accent="emerald" />
          </div>
        </div>

        <SectionCard title="Create Contact" eyebrow="Tonight's Fastest Path">
          <form className="space-y-4" onSubmit={handleCreateContact}>
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-200">Contact name</span>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Ava, Daniel, Mom, Jake..."
                className="h-12 w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40"
              />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-200">Relationship type</span>
                <select
                  value={relationshipType}
                  onChange={(event) => setRelationshipType(event.target.value as ContactListItem["relationship_type"])}
                  className="h-12 w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-sm text-white outline-none focus:border-cyan-300/40"
                >
                  <option value="date">Date</option>
                  <option value="friend">Friend</option>
                  <option value="coworker">Coworker</option>
                  <option value="family">Family</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <label className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-white">Dating mode</p>
                  <p className="text-xs text-slate-400">Adds attraction and strategy analysis.</p>
                </div>
                <input
                  type="checkbox"
                  checked={datingMode}
                  onChange={(event) => setDatingMode(event.target.checked)}
                  className="h-5 w-5 rounded border-white/20 bg-transparent text-cyan-300"
                />
              </label>
            </div>
            <button
              type="submit"
              disabled={creating || !name.trim()}
              className="flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-white text-sm font-semibold text-slate-950 transition hover:bg-cyan-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {creating ? "Creating..." : "Create intelligence profile"}
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>
        </SectionCard>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <SectionCard title="Tracked Contacts" eyebrow="Profiles">
          {loading ? (
            <div className="grid gap-4 md:grid-cols-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="h-36 animate-pulse rounded-[1.75rem] bg-white/[0.04]" />
              ))}
            </div>
          ) : contacts.length ? (
            <div className="grid gap-4 md:grid-cols-2">
              {contacts.map((contact) => (
                <Link
                  key={contact.id}
                  href={`/contacts/${contact.id}`}
                  className="group rounded-[1.75rem] border border-white/8 bg-white/[0.03] p-5 transition hover:border-cyan-300/40 hover:bg-white/[0.05]"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-lg font-semibold text-white">{contact.name}</p>
                      <p className="mt-1 text-sm capitalize text-slate-400">{contact.relationship_type}</p>
                    </div>
                    <ChevronRight className="h-5 w-5 text-slate-500 transition group-hover:text-cyan-200" />
                  </div>
                  <p className="mt-4 text-sm leading-6 text-slate-300">
                    {contact.top_takeaway ?? "Import a conversation to generate the real profile."}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <InlineBadge tone="neutral">{contact.message_count} msgs</InlineBadge>
                    <InlineBadge tone="neutral">{contact.import_count} imports</InlineBadge>
                    {contact.is_dating_mode ? <InlineBadge tone="warning">Dating mode</InlineBadge> : null}
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No contacts yet"
              detail="Create your first contact, then upload an export or paste a conversation block. The app will build the first intelligence profile automatically."
            />
          )}
        </SectionCard>

        <div className="space-y-6">
          <SectionCard title="Import Hub" eyebrow="iPhone First">
            <div className="space-y-4">
              <div className="rounded-[1.5rem] border border-cyan-300/20 bg-cyan-300/10 p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-semibold text-white">Best path for iPhone users</h3>
                    <p className="text-xs uppercase tracking-[0.24em] text-cyan-100/70">recommended</p>
                  </div>
                  <Upload className="h-5 w-5 text-cyan-100" />
                </div>
                <div className="mt-4 space-y-3 text-sm leading-6 text-slate-100">
                  <p>
                    Plug in your iPhone, let iTunes make an unencrypted local backup, then zip and drop that backup into TextPulse. We find chat.db inside automatically and surface every one-to-one thread so you can pick the person you want to analyze.
                  </p>
                  <p>
                    <span className="font-semibold text-white">Windows path:</span> unencrypted iTunes backup in
                    <span className="mx-1 rounded bg-slate-950/70 px-2 py-1 text-xs text-cyan-100">%APPDATA%\Apple\MobileSync\Backup</span>
                    &rarr; zip the device folder &rarr; drop it in the upload box.
                  </p>
                  <p>
                    <span className="font-semibold text-white">Mac path:</span> quit Messages and drop
                    <span className="mx-1 rounded bg-slate-950/70 px-2 py-1 text-xs text-cyan-100">~/Library/Messages/chat.db</span>
                    directly.
                  </p>
                </div>
              </div>

              {appleInstruction ? (
                <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold text-white">{appleInstruction.title}</h3>
                      <p className="text-xs uppercase tracking-[0.24em] text-slate-500">apple messages</p>
                    </div>
                    <Upload className="h-5 w-5 text-cyan-200" />
                  </div>
                  <ul className="mt-4 space-y-2 text-sm leading-6 text-slate-300">
                    {appleInstruction.steps.map((step) => (
                      <li key={step} className="flex gap-3">
                        <span className="mt-2 h-1.5 w-1.5 rounded-full bg-cyan-300" />
                        <span>{step}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Other formats still supported</p>
                <div className="mt-3 space-y-3">
                  {secondaryInstructions.map((instruction) => (
                    <div key={instruction.platform} className="rounded-[1.2rem] border border-white/8 bg-slate-950/45 p-3">
                      <p className="text-sm font-semibold text-white">{instruction.title}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        {instruction.accepted_extensions.join(", ")} accepted
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Product Story" eyebrow="Why It Feels Real">
            <div className="grid gap-4 md:grid-cols-2">
              <TrustCard
                icon={Brain}
                title="Real analysis layers"
                detail="Profiles, charts, vault tags, reply coaching, and retrieval all stay anchored to the same conversation history."
              />
              <TrustCard
                icon={Shield}
                title="Privacy posture"
                detail="The stack is built around encrypted-at-rest messaging data, scoped access, and hard-delete flows."
              />
              <TrustCard
                icon={MessagesSquare}
                title="Conversation memory"
                detail="Q&A sessions keep context over time instead of acting like isolated chatbot prompts."
              />
              <TrustCard
                icon={FolderHeart}
                title="Message vault"
                detail="Every meaningful message becomes browsable, explainable evidence instead of disappearing into a transcript."
              />
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}

function TrustCard({
  icon: Icon,
  title,
  detail,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  detail: string;
}) {
  return (
    <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-5">
      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-300/10 text-cyan-200">
        <Icon className="h-5 w-5" />
      </div>
      <h3 className="mt-4 text-base font-semibold text-white">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-300">{detail}</p>
    </div>
  );
}

function MarketingExperience() {
  return (
    <div className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[1.25fr_0.95fr]">
        <div className="rounded-[2.75rem] border border-white/8 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.16),transparent_28%),linear-gradient(160deg,rgba(15,23,42,0.96),rgba(2,6,23,0.94))] p-8 sm:p-10">
          <InlineBadge tone="success">Built for sensitive, real-world message history</InlineBadge>
          <h1 className="mt-6 max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-white sm:text-6xl">
            Turn messy transcripts into a relationship intelligence system you can actually use.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300">
            TextPulse AI ingests long conversation histories and turns them into profiles, vault tags, analytics,
            live Q&A memory, and fast reply coaching. It is designed to feel like a private operator console, not a toy chatbot.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/signup"
              className="flex h-12 items-center justify-center gap-2 rounded-full bg-white px-5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100"
            >
              Start building intelligence
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/login"
              className="flex h-12 items-center justify-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-5 text-sm text-slate-200 transition hover:bg-white/[0.08]"
            >
              Open demo workspace
              <WandSparkles className="h-4 w-4" />
            </Link>
          </div>
        </div>
        <SectionCard title="What Stakeholders See" eyebrow="Credibility">
          <div className="space-y-4">
            <CredibilityRow label="Import depth" detail="iMessage, WhatsApp, Telegram, Instagram, Android XML, CSV, paste, screenshots." />
            <CredibilityRow label="Evidence model" detail="Every insight can point back to timestamped message examples and category tags." />
            <CredibilityRow label="Operator tools" detail="Profiles, reply coach, analytics storyboards, and shareable receipt-style summaries." />
            <CredibilityRow label="Deployment posture" detail="FastAPI + Next.js with clear env boundaries, demo fallbacks, and documented go-live seams." />
          </div>
        </SectionCard>
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard title="Intelligence View" eyebrow="Profile">
          <p className="text-sm leading-6 text-slate-300">
            Read the person like a brief: key takeaways, communication style, emotional triggers, values, humor,
            relationship dynamics, dating-specific strategy, and message-backed red flags or green flags.
          </p>
        </SectionCard>
        <SectionCard title="Conversation Memory" eyebrow="Q&A">
          <p className="text-sm leading-6 text-slate-300">
            Ask nuanced questions about why they reacted a certain way, what kind of plan would land, or how to bring
            up something serious without triggering defensiveness.
          </p>
        </SectionCard>
        <SectionCard title="Reply Coach" eyebrow="Execution">
          <p className="text-sm leading-6 text-slate-300">
            Paste the newest message, get subtext analysis, multiple reply options, what to avoid, and timing guidance
            based on their real patterns instead of generic chat advice.
          </p>
        </SectionCard>
      </div>
    </div>
  );
}

function CredibilityRow({ label, detail }: { label: string; detail: string }) {
  return (
    <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-4">
      <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm leading-6 text-slate-200">{detail}</p>
    </div>
  );
}

function BootScreen() {
  return (
    <div className="grid min-h-[60vh] place-items-center">
        <div className="rounded-[2rem] border border-white/8 bg-slate-950/65 px-8 py-10 text-center backdrop-blur-xl">
          <div className="mx-auto h-12 w-12 animate-spin rounded-full border-2 border-cyan-300/20 border-t-cyan-300" />
          <h2 className="mt-5 text-xl font-semibold text-white">Opening the operator workspace</h2>
          <p className="mt-2 text-sm text-slate-400">Loading identity, data mode, and your latest intelligence profiles.</p>
        </div>
      </div>
    );
}
