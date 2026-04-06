"use client";

import { startTransition, useCallback, useDeferredValue, useEffect, useState } from "react";
import { RefreshCcw, Search, Send, Sparkles, UploadCloud } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import {
  DistributionBars,
  EmojiCloud,
  HeatMap,
  RankedTopics,
  StoryLineChart,
  TrendAreaChart,
} from "@/components/charts";
import { EmptyState, InlineBadge, MetricCard, SectionCard } from "@/components/ui";
import {
  coachReply,
  confirmImport,
  createPasteImport,
  createQaSession,
  getAnalysisStatus,
  getContact,
  getImportStatus,
  getVaultCategory,
  listQaSessions,
  listVaultCategories,
  previewImport,
  regenerateAnalysis,
  retryImport,
  sendQaMessage,
} from "@/lib/api";
import type {
  ContactDetail,
  ImportContactOption,
  ImportPreviewResponse,
  ImportStatusResponse,
  QASession,
  ReplyCoachResponse,
  VaultCategoryDetail,
  VaultCategoryRead,
} from "@/lib/types";
import {
  extractChatDbFromBackupFolder,
  formatBytes,
  IOSBackupExtractionError,
  type ExtractionPhase,
} from "@/lib/ios-backup-extract";

export function ContactWorkspace({ contactId }: { contactId: string }) {
  const { token, demoMode } = useAuth();
  const [detail, setDetail] = useState<ContactDetail | null>(null);
  const [categories, setCategories] = useState<VaultCategoryRead[]>([]);
  const [categoryDetail, setCategoryDetail] = useState<VaultCategoryDetail | null>(null);
  const [sessions, setSessions] = useState<QASession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [qaInput, setQaInput] = useState("");
  const [coachInput, setCoachInput] = useState("");
  const [coachResult, setCoachResult] = useState<ReplyCoachResponse | null>(null);
  const [pasteInput, setPasteInput] = useState("");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importSource, setImportSource] = useState("imessage");
  const [contactIdentifier, setContactIdentifier] = useState("");
  const [importPreview, setImportPreview] = useState<ImportPreviewResponse | null>(null);
  const [selectedImportContact, setSelectedImportContact] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [activeImport, setActiveImport] = useState<ImportStatusResponse | null>(null);
  const [backupExtractionPhase, setBackupExtractionPhase] = useState<ExtractionPhase | null>(null);
  const [backupDeviceName, setBackupDeviceName] = useState<string | null>(null);
  const [vaultSearch, setVaultSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const deferredVaultSearch = useDeferredValue(vaultSearch);
  const refreshWorkspace = useCallback(async (nextToken?: string) => {
    const authToken = nextToken ?? token;
    if (!authToken) {
      return null;
    }
    const nextDetail = await getContact(authToken, contactId);
    startTransition(() => {
      setDetail(nextDetail);
      setCoachInput(nextDetail.recent_messages[0]?.text ?? "");
      setActiveImport(nextDetail.imports.find((item) => item.status === "processing") ?? null);
    });
    return nextDetail;
  }, [contactId, token]);

  useEffect(() => {
    if (!token) {
      return;
    }
    void Promise.all([
      getContact(token, contactId),
      listVaultCategories(token, contactId),
      listQaSessions(token, contactId),
    ])
      .then(async ([nextDetail, nextCategories, nextSessions]) => {
        const initialCategory = nextCategories[0];
        const initialCategoryDetail = initialCategory
          ? await getVaultCategory(token, contactId, initialCategory.id)
          : null;

        startTransition(() => {
          setDetail(nextDetail);
          setCategories(nextCategories);
          setCategoryDetail(initialCategoryDetail);
          setSessions(nextSessions);
          setActiveSessionId(nextSessions[0]?.id ?? null);
          setCoachInput(nextDetail.recent_messages[0]?.text ?? "");
          setActiveImport(
            nextDetail.imports.find((item) => item.status === "processing") ?? null,
          );
          setLoading(false);
        });
      })
      .catch((error) => {
        toast.error(error instanceof Error ? error.message : "Unable to load contact workspace.");
        setLoading(false);
      });
  }, [contactId, token]);

  useEffect(() => {
    const trackedImportId = activeImport?.id;
    if (!token || !trackedImportId || activeImport.status !== "processing") {
      return;
    }
    const authToken = token as string;
    const importId = trackedImportId as string;

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const nextImport = await getImportStatus(authToken, contactId, importId);
        if (cancelled) {
          return;
        }
        startTransition(() => {
          setActiveImport(nextImport);
        });

        if (nextImport.status === "completed") {
          setUploadProgress(100);
          await refreshWorkspace(authToken);
          toast.success(`Import completed: ${nextImport.message_count} new messages processed.`);
          return;
        }

        if (nextImport.status === "failed") {
          await refreshWorkspace(authToken);
          toast.error(nextImport.error_details ?? "Import failed during processing.");
          return;
        }

        timeoutId = setTimeout(() => {
          void poll();
        }, 2000);
      } catch (error) {
        if (!cancelled) {
          timeoutId = setTimeout(() => {
            void poll();
          }, 3000);
          console.error(error);
        }
      }
    }

    void poll();
    return () => {
      cancelled = true;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [activeImport, contactId, refreshWorkspace, token]);

  const activeSession = sessions.find((session) => session.id === activeSessionId) ?? null;
  const filteredVaultMessages = categoryDetail?.messages.filter((message) =>
    message.text.toLowerCase().includes(deferredVaultSearch.toLowerCase()),
  );
  const recentImports = detail?.imports?.slice(0, 5) ?? [];
  const isIPhoneImport = importSource === "imessage";

  async function handleRegenerate() {
    if (!token || !detail) {
      return;
    }
    setWorking("analysis");
    try {
      await regenerateAnalysis(token, detail.id);
      toast.success("Analysis queued. This takes a few minutes for large conversations.");
      // Poll for completion, then refresh the workspace
      const poll = setInterval(async () => {
        try {
          const status = await getAnalysisStatus(token, detail.id);
          if (status.status === "completed") {
            clearInterval(poll);
            await refreshWorkspace(token);
            setWorking(null);
            toast.success("Profile read complete!");
          } else if (status.status === "failed") {
            clearInterval(poll);
            setWorking(null);
            toast.error(status.error || "Analysis failed.");
          }
        } catch {
          clearInterval(poll);
          setWorking(null);
        }
      }, 3000);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to refresh profile.");
      setWorking(null);
    }
  }

  async function handleCategorySelect(categoryId: string) {
    if (!token) {
      return;
    }
    setWorking("vault");
    try {
      const nextDetail = await getVaultCategory(token, contactId, categoryId);
      setCategoryDetail(nextDetail);
    } finally {
      setWorking(null);
    }
  }

  async function handleSendQa() {
    if (!token || !detail || !qaInput.trim()) {
      return;
    }
    setWorking("qa");
    try {
      let sessionId = activeSessionId;
      if (!sessionId) {
        const created = await createQaSession(token, contactId);
        setSessions((current) => [created, ...current]);
        setActiveSessionId(created.id);
        sessionId = created.id;
      }
      const reply = await sendQaMessage(token, contactId, sessionId, qaInput.trim());
      setSessions((current) => {
        const nextMessagePair = [
          {
            id: `user-${Date.now()}`,
            role: "user" as const,
            content: qaInput.trim(),
            created_at: new Date().toISOString(),
          },
          {
            id: `assistant-${Date.now()}`,
            role: "assistant" as const,
            content: reply.answer,
            created_at: new Date().toISOString(),
          },
        ];
        const exists = current.some((session) => session.id === sessionId);
        if (!exists) {
          return [
            {
              id: sessionId,
              created_at: new Date().toISOString(),
              messages: nextMessagePair,
            },
            ...current,
          ];
        }
        return current.map((session) =>
          session.id === sessionId
            ? {
                ...session,
                messages: [...session.messages, ...nextMessagePair],
              }
            : session,
        );
      });
      setQaInput("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to send question.");
    } finally {
      setWorking(null);
    }
  }

  async function handleCoach() {
    if (!token || !coachInput.trim()) {
      return;
    }
    setWorking("coach");
    try {
      const response = await coachReply(token, contactId, coachInput.trim());
      setCoachResult(response);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to generate reply coaching.");
    } finally {
      setWorking(null);
    }
  }

  async function handlePasteImport() {
    if (!token || !pasteInput.trim()) {
      return;
    }
    setWorking("import");
    try {
      const response = await createPasteImport(token, contactId, pasteInput.trim());
      setActiveImport(response.import_record);
      await refreshWorkspace(token);
      toast.success("Pasted conversation staged and profile refreshed.");
      setPasteInput("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to run paste import.");
    } finally {
      setWorking(null);
    }
  }

  async function handleSelectBackupFolder(files: FileList | null) {
    if (!files || files.length === 0) {
      return;
    }
    setWorking("extract");
    setBackupExtractionPhase("locating-manifest");
    setBackupDeviceName(null);
    setImportPreview(null);
    setSelectedImportContact("");
    setUploadProgress(0);
    try {
      const extracted = await extractChatDbFromBackupFolder(files, (progress) => {
        setBackupExtractionPhase(progress.phase);
        if (progress.deviceName !== undefined) {
          setBackupDeviceName(progress.deviceName);
        }
      });
      setImportFile(extracted.file);
      setBackupDeviceName(extracted.deviceName);
      toast.success(
        `Found chat.db (${formatBytes(extracted.byteLength)})${
          extracted.deviceName ? ` from ${extracted.deviceName}` : ""
        }. Ready to scan.`
      );
    } catch (error) {
      const message =
        error instanceof IOSBackupExtractionError
          ? error.userFacing
          : error instanceof Error
            ? error.message
            : "Could not read that backup folder.";
      toast.error(message);
      setBackupExtractionPhase(null);
    } finally {
      setWorking((current) => (current === "extract" ? null : current));
    }
  }

  async function handleBuildImportPreview() {
    if (!token || !importFile) {
      return;
    }
    setWorking("upload");
    setUploadProgress(0);
    try {
      const preview = await previewImport(
        token,
        contactId,
        importFile,
        importSource,
        contactIdentifier.trim() || undefined,
        setUploadProgress,
      );
      setImportPreview(preview);
      setSelectedImportContact(
        preview.selection_required ? preview.contact_options[0]?.identifier ?? "" : contactIdentifier.trim(),
      );
      toast.success("Preview generated. Review the parsed timeline before confirming.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to build import preview.");
    } finally {
      setWorking(null);
    }
  }

  async function handleConfirmImport() {
    if (!token || !importPreview?.preview_id) {
      return;
    }
    setWorking("confirm");
    try {
      const response = await confirmImport(
        token,
        contactId,
        importPreview.preview_id,
        importPreview.selection_required ? selectedImportContact || undefined : contactIdentifier.trim() || undefined,
      );
      setActiveImport(response.import_record);
      setImportPreview(null);
      setImportFile(null);
      setContactIdentifier("");
      await refreshWorkspace(token);
      toast.success("Import confirmed. Processing has started in the background.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to confirm import.");
    } finally {
      setWorking(null);
    }
  }

  async function handleRetryImport(importId: string) {
    if (!token) {
      return;
    }
    setWorking(`retry:${importId}`);
    try {
      const nextImport = await retryImport(token, contactId, importId);
      setActiveImport(nextImport);
      await refreshWorkspace(token);
      toast.success("Import retry queued.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to retry import.");
    } finally {
      setWorking(null);
    }
  }

  function handleSelectImportContact(option: ImportContactOption) {
    setSelectedImportContact(option.identifier);
    setContactIdentifier(option.identifier);
  }

  if (loading || !detail || !detail.profile) {
    return (
      <div className="grid min-h-[50vh] place-items-center">
        <div className="rounded-[2rem] border border-white/8 bg-slate-950/65 px-8 py-10 text-center">
          <div className="mx-auto h-12 w-12 animate-spin rounded-full border-2 border-cyan-300/20 border-t-cyan-300" />
          <p className="mt-5 text-lg font-semibold text-white">Assembling the intelligence profile</p>
          <p className="mt-2 text-sm text-slate-400">Loading profile sections, analytics, predictive signals, and coaching context.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-[2.5rem] border border-white/8 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.16),transparent_32%),linear-gradient(155deg,rgba(15,23,42,0.96),rgba(2,6,23,0.94))] p-7">
          <div className="flex flex-wrap items-center gap-3">
            <InlineBadge tone={detail.profile.freshness.stale ? "warning" : "success"}>
              {detail.profile.freshness.stale ? "Needs refresh" : "Fresh profile"}
            </InlineBadge>
            {detail.is_dating_mode ? <InlineBadge tone="warning">Dating mode active</InlineBadge> : null}
            {demoMode ? <InlineBadge tone="neutral">Demo-backed UX available</InlineBadge> : null}
          </div>
          <div className="mt-5 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.28em] text-cyan-300/70">{detail.relationship_type} intelligence profile</p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">{detail.name}</h1>
              <p className="mt-4 max-w-3xl text-base leading-7 text-slate-300">
                {detail.profile.personality_overview.summary}
              </p>
            </div>
            <button
              type="button"
              onClick={handleRegenerate}
              className="inline-flex h-12 items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-sm text-slate-100 transition hover:bg-white/[0.08]"
            >
              <RefreshCcw className={`h-4 w-4 ${working === "analysis" ? "animate-spin" : ""}`} />
              Refresh profile
            </button>
          </div>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <MetricCard label="Interest Score" value={detail.profile.dating_mode?.interest_level_score ?? 8} hint="Composite signal from pace, reciprocity, and planning." />
            <MetricCard label="Ghost Probability" value={`${detail.profile.viral_signals.ghost_probability}%`} hint="Behavioral risk signal, not a certainty." accent="amber" />
            <MetricCard label="Heat Index" value={`${detail.profile.viral_signals.heat_index}%`} hint="How emotionally or romantically charged the connection currently reads." accent="emerald" />
          </div>
        </div>

        <SectionCard title="Key Takeaways" eyebrow="Executive Brief">
          <div className="space-y-4">
            {detail.profile.key_takeaways.map((takeaway) => (
              <div key={takeaway.title} className="rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-4">
                <p className="text-sm font-semibold text-white">{takeaway.title}</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">{takeaway.detail}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <SectionCard title="Predictive Profile" eyebrow="Human Read">
          <div className="space-y-5">
            <ProfileBlock title="Communication Style" body={detail.profile.communication_style.summary} />
            <ProfileBlock title="Emotional Landscape" body={detail.profile.emotional_landscape.summary} />
            <ProfileBlock title="Values & Interests" body={detail.profile.values_and_interests.summary} />
            <ProfileBlock title="Humor Profile" body={detail.profile.humor_profile.summary} />
            <ProfileBlock title="Relationship Dynamics" body={detail.profile.relationship_dynamics.summary} />
            {detail.profile.dating_mode ? (
              <ProfileBlock title="The Play" body={detail.profile.dating_mode.the_play} accent />
            ) : null}
          </div>
        </SectionCard>

        <SectionCard title="Relationship Receipt" eyebrow="Shareable Summary">
          <div className="rounded-[2rem] border border-white/8 bg-gradient-to-br from-cyan-300/10 via-slate-900 to-amber-300/10 p-5">
            <p className="text-xs uppercase tracking-[0.24em] text-slate-400">
              {detail.profile.viral_signals.receipt.headline}
            </p>
            <p className="mt-4 text-2xl font-semibold text-white">
              {detail.profile.viral_signals.receipt.one_line_roast}
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <ReceiptList title="Top Traits" items={detail.profile.viral_signals.receipt.top_traits} />
              <ReceiptList title="Catchphrases" items={detail.profile.viral_signals.receipt.catchphrases} />
              <ReceiptList title="Green Flags" items={detail.profile.viral_signals.receipt.green_flags} />
              <ReceiptList title="Red Flags" items={detail.profile.viral_signals.receipt.red_flags} />
            </div>
          </div>
        </SectionCard>
      </div>

      <section className="grid gap-6 xl:grid-cols-2">
        <SectionCard title="Conversation Story" eyebrow="Analytics">
          <TrendAreaChart data={detail.analytics.message_volume} />
        </SectionCard>
        <SectionCard title="Response Pattern" eyebrow="Cadence">
          <DistributionBars data={detail.analytics.response_time_distribution} />
        </SectionCard>
        <SectionCard title="Message Length Trend" eyebrow="Pacing">
          <StoryLineChart data={detail.analytics.message_length_trends} />
        </SectionCard>
        <SectionCard title="Activity Heatmap" eyebrow="When They Are Most Active">
          <HeatMap data={detail.analytics.activity_heatmap} />
        </SectionCard>
        <SectionCard title="Top Topics" eyebrow="What Pulls Engagement">
          <RankedTopics topics={detail.analytics.top_topics} />
        </SectionCard>
        <SectionCard title="Emoji Signature" eyebrow="Expressiveness">
          <EmojiCloud data={detail.analytics.emoji_usage} />
        </SectionCard>
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <SectionCard title="Interactive Q&A" eyebrow="Ask With Context">
          <div className="mb-4 flex flex-wrap gap-2">
            {sessions.map((session) => (
              <button
                key={session.id}
                type="button"
                onClick={() => setActiveSessionId(session.id)}
                className={`rounded-full px-3 py-2 text-xs transition ${
                  session.id === activeSessionId
                    ? "bg-white text-slate-950"
                    : "border border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]"
                }`}
              >
                Session {session.id.slice(-4)}
              </button>
            ))}
          </div>
          <div className="max-h-[24rem] space-y-3 overflow-auto pr-1">
            {activeSession?.messages.length ? (
              activeSession.messages.map((message) => (
                <div
                  key={message.id}
                  className={`rounded-[1.5rem] p-4 text-sm leading-6 ${
                    message.role === "assistant"
                      ? "border border-cyan-300/20 bg-cyan-300/10 text-slate-100"
                      : "border border-white/8 bg-white/[0.03] text-slate-300"
                  }`}
                >
                  {message.content}
                </div>
              ))
            ) : (
              <EmptyState
                title="No Q&A yet"
                detail="Ask about subtext, timing, apology strategy, gift ideas, or what their behavior likely means."
              />
            )}
          </div>
          <div className="mt-4 flex gap-3">
            <textarea
              value={qaInput}
              onChange={(event) => setQaInput(event.target.value)}
              placeholder="Why did they go cold after we made plans?"
              className="min-h-28 flex-1 rounded-[1.5rem] border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40"
            />
            <button
              type="button"
              onClick={handleSendQa}
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white text-slate-950 transition hover:bg-cyan-100"
            >
              <Send className={`h-4 w-4 ${working === "qa" ? "animate-pulse" : ""}`} />
            </button>
          </div>
        </SectionCard>

        <SectionCard title="Reply Coach" eyebrow="Paste Latest Message">
          <textarea
            value={coachInput}
            onChange={(event) => setCoachInput(event.target.value)}
            placeholder="I'm slammed today but I still want to see you this week."
            className="min-h-28 w-full rounded-[1.5rem] border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40"
          />
          <button
            type="button"
            onClick={handleCoach}
            className="mt-4 inline-flex h-12 items-center justify-center gap-2 rounded-2xl bg-white px-4 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100"
          >
            <Sparkles className={`h-4 w-4 ${working === "coach" ? "animate-pulse" : ""}`} />
            Generate coaching
          </button>
          {coachResult ? (
            <div className="mt-5 space-y-4">
              <div className="rounded-[1.5rem] border border-cyan-300/20 bg-cyan-300/10 p-4 text-sm leading-6 text-slate-100">
                {coachResult.subtext_analysis}
              </div>
              {coachResult.reply_options.map((option) => (
                <div key={option.label} className="rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">{option.label}</p>
                      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">{option.tone}</p>
                    </div>
                    <InlineBadge tone="neutral">{option.what_it_signals}</InlineBadge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-100">{option.message}</p>
                  <p className="mt-2 text-sm text-slate-400">{option.likely_reaction}</p>
                </div>
              ))}
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-[1.5rem] border border-rose-400/20 bg-rose-400/10 p-4">
                  <p className="text-sm font-semibold text-rose-100">Danger zone</p>
                  <ul className="mt-2 space-y-2 text-sm text-rose-100/90">
                    {coachResult.danger_zones.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-4 text-sm text-slate-200">
                  <p className="font-semibold text-white">Timing recommendation</p>
                  <p className="mt-2">{coachResult.timing_recommendation}</p>
                  <p className="mt-4 font-semibold text-white">Escalation guidance</p>
                  <p className="mt-2">{coachResult.escalation_guidance}</p>
                </div>
              </div>
            </div>
          ) : null}
        </SectionCard>
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <SectionCard title="Message Vault" eyebrow="Evidence Archive">
          <div className="space-y-3">
            {categories.map((category) => (
              <button
                key={category.id}
                type="button"
                onClick={() => handleCategorySelect(category.id)}
                className={`flex w-full items-center justify-between rounded-[1.3rem] px-4 py-3 text-left transition ${
                  category.id === categoryDetail?.category.id
                    ? "border border-cyan-300/25 bg-cyan-300/10"
                    : "border border-white/8 bg-white/[0.03] hover:bg-white/[0.05]"
                }`}
              >
                <div>
                  <p className="text-sm font-semibold text-white">
                    {category.emoji} {category.name}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">{category.description}</p>
                </div>
                <InlineBadge tone="neutral">{category.count}</InlineBadge>
              </button>
            ))}
          </div>
        </SectionCard>

        <SectionCard title={categoryDetail?.category.name ?? "Category feed"} eyebrow="Tagged Moments">
          {categoryDetail ? (
            <>
              <div className="mb-4 flex items-center gap-3 rounded-[1.25rem] border border-white/8 bg-white/[0.03] px-4 py-3">
                <Search className="h-4 w-4 text-slate-500" />
                <input
                  value={vaultSearch}
                  onChange={(event) => setVaultSearch(event.target.value)}
                  placeholder="Search this category..."
                  className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-500"
                />
              </div>
              <div className="space-y-4">
                {(filteredVaultMessages ?? []).map((message) => (
                  <div key={message.message_id} className="rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-4">
                    <p className="text-sm leading-6 text-slate-100">{message.text}</p>
                    <p className="mt-2 text-xs uppercase tracking-[0.22em] text-slate-500">
                      {new Date(message.timestamp).toLocaleString()}
                    </p>
                    <p className="mt-3 text-sm text-slate-400">{message.reasoning}</p>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <EmptyState title="No category selected" detail="Choose a vault category to inspect its message feed and supporting context." />
          )}
        </SectionCard>
      </section>

      <SectionCard title="Import More Data" eyebrow="Keep Intelligence Fresh">
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-5">
            <p className="text-sm font-semibold text-white">Quick paste import</p>
            <textarea
              value={pasteInput}
              onChange={(event) => setPasteInput(event.target.value)}
              placeholder="Paste a fresh conversation block here to simulate a quick import or stitch in missing context."
              className="mt-4 min-h-36 w-full rounded-[1.5rem] border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40"
            />
            <button
              type="button"
              onClick={handlePasteImport}
              className="mt-5 inline-flex h-12 items-center justify-center gap-2 rounded-2xl bg-white px-4 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100"
            >
              <UploadCloud className={`h-4 w-4 ${working === "import" ? "animate-pulse" : ""}`} />
              Run paste import
            </button>
          </div>

          <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-5">
            <p className="text-sm font-semibold text-white">File-based import</p>
            <p className="mt-2 text-xs leading-5 text-slate-400">
              {isIPhoneImport
                ? "This flow is optimized for Apple Messages. Upload one `chat.db`, pick the person from your message history, then confirm the import."
                : "Large exports now run through a staged workflow: upload once for preview, verify the parse, then confirm and let the worker finish the import in the background."}
            </p>
            {isIPhoneImport ? (
              <div className="mt-4 rounded-[1.5rem] border border-cyan-300/20 bg-cyan-300/10 p-4">
                <p className="text-sm font-semibold text-white">iPhone on Windows (recommended)</p>
                <ol className="mt-3 space-y-2 text-sm leading-6 text-slate-100 list-decimal list-inside">
                  <li>
                    Plug the iPhone into this PC and open iTunes. Under Summary, uncheck
                    <span className="mx-1 rounded bg-slate-950/70 px-2 py-1 text-xs text-cyan-100">Encrypt local backup</span>
                    and click Back Up Now.
                  </li>
                  <li>
                    When it finishes, open
                    <span className="mx-1 rounded bg-slate-950/70 px-2 py-1 text-xs text-cyan-100">%APPDATA%\Apple\MobileSync\Backup</span>
                    and note the newest device folder (its name is a long device ID).
                  </li>
                  <li>
                    Click <span className="font-semibold text-white">Pick iTunes backup folder</span> below and point it at that device folder. Your phone backup stays on this computer &mdash; TextPulse only uploads the chat.db it finds inside.
                  </li>
                </ol>
                <label
                  className={`mt-4 flex min-h-24 cursor-pointer flex-col items-center justify-center rounded-[1.25rem] border border-dashed border-cyan-300/40 bg-slate-950/50 px-4 py-3 text-center text-sm text-slate-100 transition hover:bg-slate-950/70 ${working === "extract" ? "opacity-70" : ""}`}
                >
                  <input
                    type="file"
                    className="hidden"
                    /* @ts-expect-error -- directory picker attributes are non-standard but widely supported */
                    webkitdirectory=""
                    directory=""
                    multiple
                    onChange={(event) => void handleSelectBackupFolder(event.target.files)}
                  />
                  <UploadCloud className={`h-5 w-5 text-cyan-200 ${working === "extract" ? "animate-pulse" : ""}`} />
                  <p className="mt-2 font-semibold text-white">
                    {working === "extract"
                      ? extractionPhaseLabel(backupExtractionPhase)
                      : backupDeviceName && importFile?.name === "chat.db"
                        ? `Found chat.db on ${backupDeviceName} (${formatBytes(importFile.size)})`
                        : importFile?.name === "chat.db" && backupExtractionPhase === "done"
                          ? `chat.db ready (${formatBytes(importFile.size)})`
                          : "Pick iTunes backup folder"}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    Your backup never leaves this PC &mdash; only chat.db is extracted and uploaded.
                  </p>
                </label>
                <p className="mt-3 text-xs text-slate-300">
                  On a Mac? Skip the backup &mdash; just quit Messages and drop
                  <span className="mx-1 rounded bg-slate-950/70 px-2 py-1 text-xs text-cyan-100">~/Library/Messages/chat.db</span>
                  into the file picker below.
                </p>
              </div>
            ) : null}
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <select
                  value={importSource}
                  onChange={(event) => {
                    setImportSource(event.target.value);
                    setImportPreview(null);
                    setSelectedImportContact("");
                    setUploadProgress(0);
                  }}
                className="h-12 rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-sm text-white outline-none focus:border-cyan-300/40"
              >
                <option value="imessage">iMessage</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="telegram">Telegram</option>
                <option value="instagram">Instagram</option>
                <option value="android_sms">Android SMS</option>
                <option value="csv">CSV / TXT</option>
                <option value="screenshot">Screenshot</option>
              </select>
                <input
                  value={contactIdentifier}
                  onChange={(event) => {
                    setContactIdentifier(event.target.value);
                    setSelectedImportContact(event.target.value);
                    setImportPreview(null);
                  }}
                  placeholder={isIPhoneImport ? "Phone number or email if you already know it" : "Optional contact identifier"}
                  className="h-12 rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40"
                />
            </div>
            <label className="mt-4 flex min-h-32 cursor-pointer flex-col items-center justify-center rounded-[1.5rem] border border-dashed border-white/12 bg-white/[0.02] px-4 text-center text-sm text-slate-300">
                <input
                  type="file"
                  className="hidden"
                  onChange={(event) => {
                    setImportFile(event.target.files?.[0] ?? null);
                    setImportPreview(null);
                    setSelectedImportContact("");
                    setUploadProgress(0);
                  }}
                />
              <UploadCloud className="h-6 w-6 text-cyan-200" />
              <p className="mt-3 font-medium text-white">
                {importFile ? importFile.name : "Choose a chat export or screenshot"}
              </p>
              {importFile ? (
                <p className="mt-2 text-xs text-slate-400">
                  {formatFileSize(importFile.size)} ready to upload
                </p>
              ) : null}
              <p className="mt-2 text-xs text-slate-500">
                {isIPhoneImport
                  ? "For live Mac databases, quitting Messages before copying `chat.db` gives the cleanest snapshot."
                  : "Supports files up to roughly 150 MB per upload. TXT and CSV are the best path for large transcript tests."}
              </p>
            </label>
              <button
                type="button"
                onClick={handleBuildImportPreview}
                disabled={!importFile}
                className="mt-5 inline-flex h-12 items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold text-white transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-60"
              >
                <UploadCloud className={`h-4 w-4 ${working === "upload" ? "animate-pulse" : ""}`} />
                {isIPhoneImport ? "Scan Messages database" : "Build import preview"}
              </button>
            {importPreview ? (
              <div className="mt-5 rounded-[1.5rem] border border-cyan-300/20 bg-cyan-300/10 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">
                      {importPreview.selection_required ? "Choose the person from Messages" : "Preview ready to confirm"}
                    </p>
                    <p className="mt-1 text-xs text-cyan-100/80">
                      {importPreview.selection_required
                        ? `We scanned ${importPreview.file_name} and found likely one-to-one Apple Messages threads.`
                        : `${importPreview.message_count} parsed messages from ${importPreview.file_name}`}
                    </p>
                  </div>
                  <InlineBadge tone="success">Preview staged</InlineBadge>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <ImportStat
                    label={importPreview.selection_required ? "Threads found" : "Messages"}
                    value={importPreview.selection_required ? importPreview.contact_options.length : importPreview.message_count}
                  />
                  <ImportStat
                    label="Contact"
                    value={importPreview.selection_required ? "Pick below" : Number(importPreview.stats.contact_messages ?? 0)}
                  />
                  <ImportStat
                    label="User"
                    value={importPreview.selection_required ? "Auto-detected" : Number(importPreview.stats.user_messages ?? 0)}
                  />
                  <ImportStat
                    label="Date range"
                    value={formatDateRange(importPreview.date_range.start, importPreview.date_range.end)}
                  />
                </div>
                {importPreview.selection_required ? (
                  <div className="mt-4 rounded-[1.25rem] border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Likely people in this database</p>
                    <div className="mt-3 space-y-3">
                      {importPreview.contact_options.slice(0, 8).map((option) => (
                        <button
                          key={option.identifier}
                          type="button"
                          onClick={() => handleSelectImportContact(option)}
                          className={`flex w-full items-start justify-between gap-4 rounded-[1rem] border p-3 text-left transition ${
                            selectedImportContact === option.identifier
                              ? "border-cyan-300/30 bg-cyan-300/10"
                              : "border-white/8 bg-white/[0.03] hover:bg-white/[0.06]"
                          }`}
                        >
                          <div>
                            <p className="text-sm font-semibold text-white">{option.label}</p>
                            <p className="mt-1 text-xs text-slate-400">{option.identifier}</p>
                            <p className="mt-2 text-xs uppercase tracking-[0.18em] text-slate-500">
                              {option.total_messages} total | {option.received_messages} received | {option.sent_messages} sent
                            </p>
                          </div>
                          <InlineBadge tone={selectedImportContact === option.identifier ? "success" : "neutral"}>
                            {option.latest_message_at ? new Date(option.latest_message_at).toLocaleDateString() : "No date"}
                          </InlineBadge>
                        </button>
                      ))}
                    </div>
                    <p className="mt-3 text-xs leading-5 text-slate-400">
                      If the right person is not listed, enter their phone number or email above and scan again.
                    </p>
                  </div>
                ) : (
                  <div className="mt-4 rounded-[1.25rem] border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Sample messages</p>
                    <div className="mt-3 space-y-3">
                      {importPreview.previews.slice(0, 5).map((message) => (
                        <div key={message.canonical_id} className="rounded-[1rem] border border-white/8 bg-white/[0.03] p-3">
                          <div className="flex items-center justify-between gap-3 text-xs uppercase tracking-[0.18em] text-slate-500">
                            <span>{message.sender}</span>
                            <span>{new Date(message.timestamp).toLocaleString()}</span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-100">{message.text}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={handleConfirmImport}
                    disabled={importPreview.selection_required && !selectedImportContact}
                    className="inline-flex h-12 items-center justify-center gap-2 rounded-2xl bg-white px-4 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <UploadCloud className={`h-4 w-4 ${working === "confirm" ? "animate-pulse" : ""}`} />
                    {importPreview.selection_required ? "Import selected person" : "Confirm import"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setImportPreview(null)}
                    className="inline-flex h-12 items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-sm font-semibold text-white transition hover:bg-white/[0.08]"
                  >
                    Clear preview
                  </button>
                </div>
              </div>
            ) : null}
            {working === "upload" || working === "confirm" || activeImport ? (
                <div className="mt-5 rounded-[1.5rem] border border-white/8 bg-slate-950/60 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">
                        {working === "upload"
                          ? "Uploading transcript for preview"
                          : working === "confirm"
                            ? "Queueing confirmed import"
                          : activeImport?.status === "completed"
                            ? "Import completed"
                            : activeImport?.status === "failed"
                              ? "Import failed"
                              : "Processing import"}
                    </p>
                    <p className="mt-1 text-xs text-slate-400">
                      {activeImport?.file_name ?? importFile?.name ?? "Preparing upload"}
                    </p>
                  </div>
                  <InlineBadge
                    tone={
                      activeImport?.status === "failed"
                        ? "warning"
                        : activeImport?.status === "completed"
                          ? "success"
                          : "neutral"
                    }
                    >
                      {working === "upload"
                        ? `${uploadProgress}% uploaded`
                        : working === "confirm"
                          ? "queueing"
                        : activeImport?.status ?? "processing"}
                    </InlineBadge>
                  </div>
                  <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/[0.06]">
                  <div
                    className={`h-full rounded-full ${
                      activeImport?.status === "failed" ? "bg-rose-400" : "bg-cyan-300"
                    }`}
                      style={{
                        width: `${
                          working === "upload"
                            ? Math.max(uploadProgress, 6)
                            : working === "confirm"
                              ? 96
                            : activeImport?.status === "completed"
                              ? 100
                              : activeImport?.status === "failed"
                                ? 100
                                : 92
                      }%`,
                    }}
                  />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
                    {importPreview && working === "upload" ? <span>Uploading once to stage the preview.</span> : null}
                    {activeImport?.message_count ? <span>{activeImport.message_count} messages imported</span> : null}
                    {activeImport?.error_details ? <span>{activeImport.error_details}</span> : null}
                  </div>
                  {activeImport?.status === "failed" ? (
                    <button
                      type="button"
                      onClick={() => handleRetryImport(activeImport.id)}
                      className="mt-4 inline-flex h-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] px-3 text-xs font-semibold text-white transition hover:bg-white/[0.08]"
                    >
                      {working === `retry:${activeImport.id}` ? "Retrying..." : "Retry failed import"}
                    </button>
                  ) : null}
                </div>
              ) : null}
          </div>
        </div>
        <div className="mt-5 rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">Import activity</p>
              <p className="mt-1 text-xs text-slate-400">
                Latest uploads and parsing outcomes for this contact.
              </p>
            </div>
            <InlineBadge tone="neutral">{recentImports.length} recent</InlineBadge>
          </div>
          <div className="mt-4 space-y-3">
            {recentImports.length ? (
              recentImports.map((item) => (
                <div key={item.id} className="flex flex-col gap-2 rounded-[1.25rem] border border-white/8 bg-slate-950/45 p-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-white">{item.file_name}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.22em] text-slate-500">
                      {item.source_platform} | {new Date(item.imported_at).toLocaleString()}
                    </p>
                    <p className="mt-2 text-sm text-slate-300">
                      {item.status === "completed"
                        ? `${item.message_count} messages imported`
                        : item.status === "failed"
                          ? item.error_details ?? "Import failed during parsing."
                          : "Still processing in the background."}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {item.status === "failed" ? (
                      <button
                        type="button"
                        onClick={() => handleRetryImport(item.id)}
                        className="inline-flex h-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] px-3 text-xs font-semibold text-white transition hover:bg-white/[0.08]"
                      >
                        {working === `retry:${item.id}` ? "Retrying..." : "Retry import"}
                      </button>
                    ) : null}
                    <InlineBadge
                      tone={
                        item.status === "completed"
                          ? "success"
                          : item.status === "failed"
                            ? "warning"
                            : "neutral"
                      }
                    >
                      {item.status}
                    </InlineBadge>
                  </div>
                </div>
              ))
            ) : (
              <EmptyState
                title="No import activity yet"
                detail="Upload a TXT, CSV, chat export, or screenshot to populate the timeline and refresh the profile."
              />
            )}
          </div>
        </div>
      </SectionCard>
    </div>
  );
}

function ProfileBlock({ title, body, accent }: { title: string; body: string; accent?: boolean }) {
  return (
    <div className={`rounded-[1.5rem] border p-4 ${accent ? "border-cyan-300/20 bg-cyan-300/10" : "border-white/8 bg-white/[0.03]"}`}>
      <p className="text-sm font-semibold text-white">{title}</p>
      <p className="mt-2 text-sm leading-6 text-slate-300">{body}</p>
    </div>
  );
}

function ReceiptList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-[1.25rem] border border-white/8 bg-white/[0.03] p-4">
      <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{title}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.length ? items.map((item) => <InlineBadge key={item}>{item}</InlineBadge>) : <InlineBadge>None yet</InlineBadge>}
      </div>
    </div>
  );
}

function ImportStat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-[1rem] border border-white/10 bg-slate-950/45 p-3">
      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function extractionPhaseLabel(phase: ExtractionPhase | null): string {
  switch (phase) {
    case "locating-manifest":
      return "Looking for Manifest.db...";
    case "reading-manifest":
      return "Reading Manifest.db from the backup...";
    case "loading-sqlite":
      return "Loading SQLite reader...";
    case "querying-manifest":
      return "Finding chat.db in the backup index...";
    case "locating-chat-db":
      return "Copying chat.db out of the backup...";
    case "done":
      return "chat.db ready";
    default:
      return "Reading backup...";
  }
}

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDateRange(start: string | null, end: string | null) {
  if (!start || !end) {
    return "Unknown";
  }
  return `${new Date(start).toLocaleDateString()} - ${new Date(end).toLocaleDateString()}`;
}
