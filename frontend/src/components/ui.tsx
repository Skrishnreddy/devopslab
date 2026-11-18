import type { ReactNode } from "react";

export function Card({ title, action, children, className = "" }: {
  title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-xl border border-ink-700 bg-ink-900 p-5 ${className}`}>
      {(title || action) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-400">{title}</h2>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, sub, tone = "default" }: {
  label: string; value: ReactNode; sub?: ReactNode; tone?: "default" | "ok" | "warn" | "bad";
}) {
  const color = { default: "text-white", ok: "text-ok", warn: "text-warn", bad: "text-bad" }[tone];
  return (
    <div className="rounded-lg bg-ink-800 px-4 py-3">
      <div className="text-xs text-ink-400">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${color}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink-400">{sub}</div>}
    </div>
  );
}

export function Progress({ percent }: { percent: number }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-ink-700" role="progressbar" aria-valuenow={percent}>
      <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${percent}%` }} />
    </div>
  );
}

const badgeTone: Record<string, string> = {
  beginner: "bg-emerald-500/15 text-emerald-300",
  intermediate: "bg-sky-500/15 text-sky-300",
  advanced: "bg-fuchsia-500/15 text-fuchsia-300",
  low: "bg-ink-700 text-ink-200",
  medium: "bg-amber-500/15 text-amber-300",
  high: "bg-orange-500/15 text-orange-300",
  critical: "bg-red-500/20 text-red-300",
  planned: "bg-ink-700 text-ink-400",
  available: "bg-emerald-500/15 text-emerald-300",
};

export function Badge({ children }: { children: string }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${badgeTone[children] ?? "bg-ink-700 text-ink-200"}`}>
      {children}
    </span>
  );
}

export function ClusterDown({ reason }: { reason?: string }) {
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
      <p className="font-medium">The lab cluster isn't running.</p>
      <p className="mt-1 text-amber-200/80">
        Start it with <code className="rounded bg-ink-950 px-1.5 py-0.5 font-mono">make up</code> in the
        devopslab folder. {reason && <span className="block mt-1 text-xs opacity-70">{reason}</span>}
      </p>
    </div>
  );
}
