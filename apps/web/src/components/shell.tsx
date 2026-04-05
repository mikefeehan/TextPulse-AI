"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck, Sparkles } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { InlineBadge } from "@/components/ui";

export function Shell({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { user, signOut, demoMode } = useAuth();

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.16),transparent_30%),radial-gradient(circle_at_top_right,rgba(245,158,11,0.14),transparent_25%),linear-gradient(180deg,rgba(2,6,23,0.98),rgba(5,10,20,1))]" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.05)_1px,transparent_1px)] bg-[size:80px_80px] opacity-20" />
      <div className="relative mx-auto flex min-h-screen max-w-[1440px] flex-col px-4 pb-8 pt-4 sm:px-6 lg:px-8">
        <header className="sticky top-4 z-20 mb-8 rounded-[2rem] border border-white/8 bg-slate-950/70 px-5 py-4 backdrop-blur-xl">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-300 via-teal-300 to-amber-300 text-slate-950 shadow-[0_12px_30px_rgba(56,189,248,0.3)]">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <Link href="/" className="text-lg font-semibold tracking-tight text-white">
                  TextPulse AI
                </Link>
                <p className="text-sm text-slate-400">
                  Relationship intelligence, reply coaching, and conversation analytics.
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <nav className="flex items-center gap-2 rounded-full border border-white/8 bg-white/[0.03] p-1">
                <Link
                  href="/"
                  className={`rounded-full px-4 py-2 text-sm transition ${
                    pathname === "/" ? "bg-white text-slate-950" : "text-slate-300 hover:bg-white/[0.06]"
                  }`}
                >
                  Dashboard
                </Link>
                <Link
                  href={user ? `/contacts/c-ava` : "/login"}
                  className={`rounded-full px-4 py-2 text-sm transition ${
                    pathname?.startsWith("/contacts")
                      ? "bg-white text-slate-950"
                      : "text-slate-300 hover:bg-white/[0.06]"
                  }`}
                >
                  Intelligence
                </Link>
              </nav>

              <div className="flex items-center gap-3">
                {demoMode ? <InlineBadge tone="warning">Demo-backed mode</InlineBadge> : null}
                <div className="hidden items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-2 text-xs text-emerald-200 md:flex">
                  <ShieldCheck className="h-4 w-4" />
                  Encrypted workflow
                </div>
                {user ? (
                  <button
                    type="button"
                    onClick={signOut}
                    className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-slate-200 transition hover:bg-white/[0.08]"
                  >
                    Sign out
                  </button>
                ) : (
                  <div className="flex gap-2">
                    <Link
                      href="/login"
                      className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-slate-200 transition hover:bg-white/[0.08]"
                    >
                      Log in
                    </Link>
                    <Link
                      href="/signup"
                      className="rounded-full bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-100"
                    >
                      Start free
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
