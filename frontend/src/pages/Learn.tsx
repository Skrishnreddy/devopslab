import { CheckCircle2, Circle } from "lucide-react";
import { api, type Level } from "../api";
import { useApi } from "../useApi";
import { Badge, Card, Progress } from "../components/ui";

const LEVELS: { id: Level; blurb: string }[] = [
  { id: "beginner", blurb: "Understand concepts and follow guided exercises" },
  { id: "intermediate", blurb: "Modify existing deployments and configurations" },
  { id: "advanced", blurb: "Troubleshoot incidents without step-by-step instructions" },
];

export default function Learn() {
  const { data: tracks, reload } = useApi(api.tracks);
  const k8s = tracks?.find((t) => t.id === "kubernetes");

  const toggle = async (id: string, completed: boolean) => {
    await api.setComplete(id, !completed);
    reload();
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Learn Mode</h1>
        <p className="mt-1 text-ink-400">Topic by topic, from concepts to hands-on to unguided troubleshooting.</p>
      </div>

      {k8s && (
        <Card title="Kubernetes track" action={<span className="text-sm text-ink-400">{k8s.progress.completed}/{k8s.progress.total} modules</span>}>
          <Progress percent={k8s.progress.percent} />
          <div className="mt-6 space-y-6">
            {LEVELS.map((lvl) => (
              <div key={lvl.id}>
                <div className="mb-2 flex items-center gap-3">
                  <Badge>{lvl.id}</Badge>
                  <span className="text-sm text-ink-400">{lvl.blurb}</span>
                </div>
                <ul className="divide-y divide-ink-700 rounded-lg border border-ink-700">
                  {k8s.modules.filter((m) => m.level === lvl.id).map((m) => (
                    <li key={m.id} className="flex items-center gap-4 px-4 py-3">
                      <button onClick={() => toggle(m.id, m.completed)}
                        aria-label={m.completed ? `Mark ${m.title} not done` : `Mark ${m.title} done`}
                        className="text-ink-400 hover:text-accent">
                        {m.completed ? <CheckCircle2 className="h-5 w-5 text-ok" /> : <Circle className="h-5 w-5" />}
                      </button>
                      <span className="w-8 font-mono text-sm text-ink-400">{String(m.order).padStart(2, "0")}</span>
                      <span className="flex-1 font-medium text-white">{m.title}</span>
                      <span className="hidden text-sm text-ink-400 sm:block">{m.task}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card title="Other tracks">
        <div className="flex flex-wrap gap-2">
          {tracks?.filter((t) => t.id !== "kubernetes").map((t) => (
            <span key={t.id} className="rounded-md bg-ink-800 px-3 py-1.5 text-sm text-ink-400">
              {t.name} <span className="text-xs">· coming soon</span>
            </span>
          ))}
        </div>
      </Card>
    </div>
  );
}
