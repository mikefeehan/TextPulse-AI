import { clsx } from "clsx";

export function SectionCard({
  title,
  eyebrow,
  children,
  className,
  action,
}: {
  title: string;
  eyebrow?: string;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
}) {
  return (
    <section
      className={clsx(
        "rounded-[2rem] border border-white/8 bg-slate-950/65 p-6 shadow-[0_24px_90px_rgba(2,6,23,0.45)] backdrop-blur-xl",
        className,
      )}
    >
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          {eyebrow ? (
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-300/70">
              {eyebrow}
            </p>
          ) : null}
          <h2 className="mt-2 text-xl font-semibold text-white">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function MetricCard({
  label,
  value,
  hint,
  accent = "cyan",
}: {
  label: string;
  value: string | number;
  hint?: string;
  accent?: "cyan" | "amber" | "emerald";
}) {
  const accents = {
    cyan: "from-cyan-300/15 to-cyan-100/5 text-cyan-100",
    amber: "from-amber-300/15 to-amber-100/5 text-amber-100",
    emerald: "from-emerald-300/15 to-emerald-100/5 text-emerald-100",
  };
  return (
    <div
      className={clsx(
        "rounded-[1.5rem] border border-white/7 bg-gradient-to-br p-5",
        accents[accent],
      )}
    >
      <p className="text-xs uppercase tracking-[0.24em] text-slate-400">{label}</p>
      <div className="mt-3 text-3xl font-semibold text-white">{value}</div>
      {hint ? <p className="mt-2 text-sm text-slate-300">{hint}</p> : null}
    </div>
  );
}

export function InlineBadge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger";
}) {
  const tones = {
    neutral: "border-white/8 bg-white/[0.04] text-slate-200",
    success: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
    warning: "border-amber-400/30 bg-amber-400/10 text-amber-100",
    danger: "border-rose-400/30 bg-rose-400/10 text-rose-200",
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

export function EmptyState({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="rounded-[1.75rem] border border-dashed border-white/10 bg-white/[0.02] px-6 py-10 text-center">
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-300">{detail}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
