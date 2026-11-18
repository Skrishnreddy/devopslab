import type { ReactNode } from "react";
import { AlertTriangle, Clock } from "lucide-react";
import type { HealthStatus } from "../api";

export function Card({ title, action, children, className = "" }: {
  title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-xl border border-ink-700 bg-ink-900 p-5 ${className}`}>
      {(title || action) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-400">{title}</h2>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold text-white">{title}</h1>
        {subtitle && <p className="mt-1 text-ink-400">{subtitle}</p>}
      </div>
      {children}
    </div>
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

export function Progress({ percent, label }: { percent: number; label?: string }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-ink-700" role="progressbar"
      aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${percent}%` }} />
    </div>
  );
}

const badgeTone: Record<string, string> = {
  beginner: "bg-emerald-500/15 text-emerald-300",
  intermediate: "bg-sky-500/15 text-sky-300",
  advanced: "bg-fuchsia-500/15 text-fuchsia-300",
  planned: "bg-ink-700 text-ink-400",
  available: "bg-emerald-500/15 text-emerald-300",
  completed: "bg-emerald-500/15 text-emerald-300",
  started: "bg-sky-500/15 text-sky-300",
  running: "bg-emerald-500/15 text-emerald-300",
  failed: "bg-red-500/15 text-red-300",
  passed: "bg-emerald-500/15 text-emerald-300",
};

export function Badge({ children, tone }: { children: string; tone?: string }) {
  return (
    <span className={`whitespace-nowrap rounded px-2 py-0.5 text-xs font-medium ${badgeTone[tone ?? children] ?? "bg-ink-700 text-ink-200"}`}>
      {children}
    </span>
  );
}

export function PlannedBadge({ phase, label = "Planned" }: { phase: number; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap rounded bg-ink-700 px-2 py-0.5 text-xs text-ink-400">
      <Clock className="h-3 w-3" /> {label} · Phase {phase}
    </span>
  );
}

const dot: Record<HealthStatus, string> = { ok: "bg-ok", warning: "bg-warn", error: "bg-bad", missing: "bg-bad" };
export function StatusDot({ status }: { status: HealthStatus }) {
  return <span className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${dot[status]}`} aria-label={status} />;
}

export function ErrorBox({ error, title = "Something went wrong" }: { error: Error; title?: string }) {
  return (
    <div role="alert" className="flex gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
      <AlertTriangle className="h-5 w-5 shrink-0" />
      <div><p className="font-medium">{title}</p><p className="mt-1 break-words text-red-200/80">{error.message}</p></div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-lg border border-dashed border-ink-700 px-4 py-6 text-center text-sm text-ink-400">{children}</p>;
}

export function Code({ children }: { children: ReactNode }) {
  return <code className="rounded bg-ink-950 px-1.5 py-0.5 font-mono text-[0.85em] text-ink-200">{children}</code>;
}

export function ClusterDown({ reason }: { reason?: string }) {
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
      <p className="font-medium">The lab cluster isn't reachable.</p>
      <p className="mt-1 text-amber-200/80">Start it with <Code>make up</Code> in the devopslab folder.</p>
      {reason && <p className="mt-2 break-words font-mono text-xs opacity-70">{reason}</p>}
    </div>
  );
}
