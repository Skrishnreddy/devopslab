import { useState } from "react";
import { CheckCircle2, Circle, CircleDot } from "lucide-react";
import { api, type Level, type Module, type ModuleStatus } from "../api";
import { useApi } from "../lib/useApi";
import { Badge, Card, ErrorBox, PageHeader, PlannedBadge, Progress } from "../components/ui";

const LEVELS: { id: Level; blurb: string }[] = [
  { id: "beginner", blurb: "Understand concepts and follow guided exercises" },
  { id: "intermediate", blurb: "Modify existing deployments and configurations" },
  { id: "advanced", blurb: "Troubleshoot incidents without step-by-step instructions" },
];
const NEXT: Record<ModuleStatus, ModuleStatus> = { not_started: "started", started: "completed", completed: "not_started" };
const ICON = { not_started: Circle, started: CircleDot, completed: CheckCircle2 };
const LABEL = { not_started: "Not started", started: "In progress", completed: "Completed" };

function ModuleRow({ m, onChange }: { m: Module; onChange: (s: ModuleStatus) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const Icon = ICON[m.status];
  const click = async () => { setBusy(true); try { await onChange(NEXT[m.status]); } finally { setBusy(false); } };
  return (
    <li className="flex items-center gap-4 px-4 py-3">
      <button onClick={click} disabled={busy} title={`${LABEL[m.status]}. Click to mark ${LABEL[NEXT[m.status]].toLowerCase()}.`}
        aria-label={`${m.title}: ${LABEL[m.status]}. Mark ${LABEL[NEXT[m.status]]}`}
        className="text-ink-400 hover:text-accent disabled:opacity-50">
        <Icon className={`h-5 w-5 ${m.status === "completed" ? "text-ok" : m.status === "started" ? "text-accent" : ""}`} />
      </button>
      <span className="w-6 font-mono text-sm text-ink-400">{String(m.order).padStart(2, "0")}</span>
      <div className="min-w-0 flex-1">
        <div className="font-medium text-white">{m.title}</div>
        <div className="text-sm text-ink-400">{m.task}</div>
      </div>
      <span className="hidden sm:block"><PlannedBadge phase={m.phase} label="Lesson" /></span>
    </li>
  );
}

export default function Learn() {
  const { data: tracks, error, reload } = useApi(api.tracks);
  const [actionError, setActionError] = useState<Error>();
  const k8s = tracks?.find((t) => t.id === "kubernetes");
  const others = tracks?.filter((t) => t.id !== "kubernetes") ?? [];

  const change = async (id: string, status: ModuleStatus) => {
    try { await api.setProgress(id, status); setActionError(undefined); await reload(); }
    catch (e) { setActionError(e as Error); }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader title="Learn Mode" subtitle="Topic by topic, from concepts to hands-on to unguided troubleshooting." />
      {error && <ErrorBox error={error} />}
      {actionError && <ErrorBox error={actionError} title="Couldn't save progress" />}
      {k8s && (
        <Card title="Kubernetes track" action={<span className="text-sm text-ink-400">{k8s.progress.completed}/{k8s.progress.total} completed</span>}>
          <Progress percent={k8s.progress.percent} label="Kubernetes progress" />
          <p className="mt-3 text-xs text-ink-400">
            Track your progress with the status icon. Full lessons, exercises with automatic checks and quizzes arrive in Phase 5.
          </p>
          <div className="mt-5 space-y-6">
            {LEVELS.map((lvl) => (
              <div key={lvl.id}>
                <div className="mb-2 flex items-center gap-3"><Badge>{lvl.id}</Badge><span className="text-sm text-ink-400">{lvl.blurb}</span></div>
                <ul className="divide-y divide-ink-700 rounded-lg border border-ink-700">
                  {k8s.modules.filter((m) => m.level === lvl.id).map((m) => (
                    <ModuleRow key={m.id} m={m} onChange={(s) => change(m.id, s)} />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Card>
      )}
      <Card title="Other tracks">
        <ul className="grid gap-3 sm:grid-cols-2">
          {others.map((t) => (
            <li key={t.id} className="rounded-lg bg-ink-800 p-3">
              <div className="flex items-center justify-between gap-2"><span className="font-medium text-white">{t.name}</span><PlannedBadge phase={t.phase} /></div>
              <p className="mt-1 text-sm text-ink-400">{t.description}</p>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
