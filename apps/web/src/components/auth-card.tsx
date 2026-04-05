"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";

export function AuthCard({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const { signIn, signUp, demoMode } = useAuth();
  const [email, setEmail] = useState("demo@textpulse.ai");
  const [password, setPassword] = useState("demo-password");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    try {
      if (mode === "login") {
        await signIn(email, password);
      } else {
        await signUp(email, password);
      }
      toast.success(mode === "login" ? "Welcome back" : "Workspace created");
      router.push("/");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto grid min-h-[75vh] max-w-6xl items-center gap-6 xl:grid-cols-[1.05fr_0.95fr]">
      <div className="rounded-[2.75rem] border border-white/8 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.16),transparent_30%),linear-gradient(160deg,rgba(15,23,42,0.96),rgba(2,6,23,0.94))] p-8 sm:p-10">
        <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-300/70">TextPulse Operator Console</p>
        <h1 className="mt-5 text-4xl font-semibold tracking-tight text-white sm:text-5xl">
          {mode === "login"
            ? "Pick up your relationship intelligence, coaching, and message insights."
            : "Stand up a private relationship intelligence workspace in minutes."}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300">
          {mode === "login"
            ? "Jump back into your contact intelligence, profile refreshes, and reply coaching without losing context."
            : "Create contacts, import transcripts, generate predictive intelligence, and keep every insight tied to real evidence."}
        </p>
        <div className="mt-8 grid gap-4 md:grid-cols-2">
          <Feature title="Evidence-backed analysis" detail="Profiles and recommendations stay grounded in actual message examples." />
          <Feature title="Reply coaching" detail="Fast subtext reads, multi-tone replies, and timing guidance." />
          <Feature title="Vault archive" detail="Browse flirty, vulnerable, funny, hurtful, or strategic messages on demand." />
          <Feature title="Demo-safe fallback" detail="Tonight's build still works even before every credential is wired up." />
        </div>
      </div>

      <div className="rounded-[2.5rem] border border-white/8 bg-slate-950/70 p-8 shadow-[0_30px_90px_rgba(2,6,23,0.5)] backdrop-blur-xl">
        <div className="mb-6">
          <p className="text-sm uppercase tracking-[0.22em] text-slate-500">
            {mode === "login" ? "Log in" : "Create account"}
          </p>
          <h2 className="mt-2 text-3xl font-semibold text-white">
            {mode === "login" ? "Welcome back" : "Start free"}
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            {demoMode
              ? "No live backend detected, so this form will still open the demo-backed workspace."
              : "Your workspace is ready to connect to the live API."}
          </p>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-200">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="h-12 w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-200">Password</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="h-12 w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40"
            />
          </label>
          <button
            type="submit"
            disabled={loading}
            className="flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-white text-sm font-semibold text-slate-950 transition hover:bg-cyan-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Working..." : mode === "login" ? "Open workspace" : "Create workspace"}
            <ArrowRight className="h-4 w-4" />
          </button>
        </form>

        <p className="mt-5 text-sm text-slate-400">
          {mode === "login" ? "Need an account?" : "Already have an account?"}{" "}
          <Link
            href={mode === "login" ? "/signup" : "/login"}
            className="font-medium text-cyan-200 transition hover:text-cyan-100"
          >
            {mode === "login" ? "Start free" : "Log in"}
          </Link>
        </p>
      </div>
    </div>
  );
}

function Feature({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-5">
      <p className="text-base font-semibold text-white">{title}</p>
      <p className="mt-2 text-sm leading-6 text-slate-300">{detail}</p>
    </div>
  );
}
