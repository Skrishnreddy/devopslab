import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { api } from "../api";
import { useApi } from "../useApi";
import { Card, ClusterDown, Progress, Stat } from "../components/ui";

export default function Dashboard() {
  const { data: c } = useApi(api.cluster, 10_000);
  const { data: tracks } = useApi(api.tracks);
  const k8s = tracks?.find((t) => t.id === "kubernetes");
  const next = k8s?.modules.find((m) => !m.completed);
  const running = c?.pods?.by_phase.Running ?? 0;
  const notRunning = (c?.pods?.total ?? 0) - running - (c?.pods?.by_phase.Succeeded ?? 0);

  return (
    <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-3">
      <Card title="Kubernetes cluster" className="lg:col-span-2">
        {!c ? (
          <p className="text-ink-400">Checking cluster…</p>
        ) : !c.connected ? (
          <ClusterDown reason={c.reason} />
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Nodes" value={`${c.nodes!.ready}/${c.nodes!.total}`} sub="Ready"
              tone={c.nodes!.ready === c.nodes!.total ? "ok" : "bad"} />
            <Stat label="Namespaces" value={c.namespaces} />
            <Stat label="Pods" value={running} sub={notRunning > 0 ? `${notRunning} not running` : "Running"}
              tone={notRunning > 0 ? "warn" : "ok"} />
            <Stat label="Deployments" value={c.deployments!.total} sub={`${c.deployments!.available} available`} />
          </div>
        )}
      </Card>

      <Card title="Continue learning">
        {next ? (
          <Link to="/learn" className="group block rounded-lg bg-ink-800 p-4 hover:bg-ink-700">
            <div className="text-xs text-ink-400">Kubernetes · Module {String(next.order).padStart(2, "0")}</div>
            <div className="mt-1 font-semibold text-white">{next.title}</div>
            <div className="mt-1 text-sm text-ink-400">{next.task}</div>
            <div className="mt-3 flex items-center gap-1 text-sm text-accent">
              Open module <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </div>
          </Link>
        ) : (
          <p className="text-ink-400">{k8s ? "Kubernetes track complete." : "Loading…"}</p>
        )}
      </Card>

      <Card title="Learning progress" className="lg:col-span-3">
        <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
          {tracks?.map((t) => (
            <div key={t.id}>
              <div className="mb-1.5 flex justify-between text-sm">
                <span className="text-white">{t.name}</span>
                <span className="tabular-nums text-ink-400">
                  {t.status === "planned" ? "soon" : `${t.progress.percent}%`}
                </span>
              </div>
              <Progress percent={t.progress.percent} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
