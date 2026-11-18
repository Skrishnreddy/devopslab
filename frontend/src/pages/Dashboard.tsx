import { Link } from "react-router-dom";
import { ArrowRight, RefreshCw } from "lucide-react";
import { api, type ClusterSummary, type InfraHealth } from "../api";
import { useApi } from "../lib/useApi";
import { ago, duration } from "../lib/format";
import { Badge, Card, ClusterDown, Code, Empty, ErrorBox, Progress, Stat, StatusDot } from "../components/ui";

function InfraCard({ data, error, reload }: { data?: InfraHealth; error?: Error; reload: () => void }) {
  return (
    <Card title="Infrastructure" className="lg:col-span-2"
      action={
        <button onClick={reload} className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-ink-400 hover:bg-ink-800 hover:text-white">
          <RefreshCw className="h-3.5 w-3.5" /> Re-check
        </button>
      }>
      {error && <ErrorBox error={error} title="Couldn't run health checks" />}
      {!data && !error && <p className="text-sm text-ink-400">Running checks…</p>}
      {data && (
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {data.components.map((c) => (
            <li key={c.id} className="rounded-lg bg-ink-800 px-3 py-2.5">
              <div className="flex items-center gap-2">
                <StatusDot status={c.status} />
                <span className="font-medium text-white">{c.name}</span>
                {c.version && <span className="ml-auto font-mono text-xs text-ink-400">{c.version}</span>}
              </div>
              <p className="mt-1 text-xs text-ink-400">{c.message}</p>
              {c.remediation && c.status !== "ok" && (
                <p className="mt-1 text-xs text-amber-300">{c.remediation.split("`").map((part, i) =>
                  i % 2 ? <Code key={i}>{part}</Code> : part)}</p>
              )}
            </li>
          ))}
        </ul>
      )}
      {data && <p className="mt-3 text-xs text-ink-400">Checked {ago(data.checked_at)}</p>}
    </Card>
  );
}

function ClusterCard({ c, error }: { c?: ClusterSummary; error?: Error }) {
  const running = c?.pods?.by_phase.Running ?? 0;
  const succeeded = c?.pods?.by_phase.Succeeded ?? 0;
  const notRunning = (c?.pods?.total ?? 0) - running - succeeded;
  return (
    <Card title="Kubernetes cluster" className="lg:col-span-2"
      action={c?.connected && <span className="font-mono text-xs text-ink-400">{c.context} · {c.server_version}</span>}>
      {error ? <ErrorBox error={error} /> : !c ? <p className="text-sm text-ink-400">Contacting API server…</p> :
        !c.connected ? <ClusterDown reason={c.reason} /> : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Nodes" value={`${c.nodes!.ready}/${c.nodes!.total}`} sub="Ready"
              tone={c.nodes!.ready === c.nodes!.total ? "ok" : "bad"} />
            <Stat label="Namespaces" value={c.namespaces} />
            <Stat label="Pods" value={c.pods!.total} sub={notRunning > 0 ? `${notRunning} not running` : `${running} running`}
              tone={notRunning > 0 ? "warn" : "ok"} />
            <Stat label="Deployments" value={c.deployments!.total} sub={`${c.deployments!.available} available`}
              tone={c.deployments!.available < c.deployments!.total ? "warn" : "default"} />
          </div>
        )}
    </Card>
  );
}

export default function Dashboard() {
  const infra = useApi(api.infra, 30_000);
  const cluster = useApi(api.cluster, 10_000);
  const tracks = useApi(api.tracks);
  const progress = useApi(api.progress);
  const labs = useApi(api.labs, 30_000);
  const activity = useApi(() => api.activity(5));
  const attempts = useApi(() => api.attempts(5));

  const k8s = tracks.data?.find((t) => t.id === "kubernetes");
  const next = k8s?.modules.find((m) => m.status === "started") ?? k8s?.modules.find((m) => m.status !== "completed");
  const activeLabs = labs.data?.filter((l) => ["running", "creating", "resetting"].includes(l.status)) ?? [];

  return (
    <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-3">
      <InfraCard data={infra.data} error={infra.error} reload={infra.reload} />

      <Card title="Continue learning">
        {tracks.error ? <ErrorBox error={tracks.error} /> : next ? (
          <Link to="/learn" className="group block rounded-lg bg-ink-800 p-4 hover:bg-ink-700">
            <div className="text-xs text-ink-400">Kubernetes · Module {String(next.order).padStart(2, "0")}</div>
            <div className="mt-1 font-semibold text-white">{next.title}</div>
            <div className="mt-1 text-sm text-ink-400">{next.task}</div>
            <div className="mt-3 flex items-center gap-1 text-sm text-accent">
              Open track <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </div>
          </Link>
        ) : <p className="text-sm text-ink-400">{k8s ? "Kubernetes track complete." : "Loading…"}</p>}
      </Card>

      <ClusterCard c={cluster.data} error={cluster.error} />

      <Card title="Active labs">
        {labs.error ? <ErrorBox error={labs.error} /> : activeLabs.length ? (
          <ul className="space-y-2">{activeLabs.map((l) => (
            <li key={l.id} className="flex items-center justify-between text-sm">
              <span className="font-mono text-white">{l.ref_id}</span><Badge>{l.status}</Badge>
            </li>))}
          </ul>
        ) : <Empty>No labs running. Deployable labs arrive with CloudMart in Phase 4.</Empty>}
      </Card>

      <Card title="Learning progress" className="lg:col-span-2"
        action={progress.data && <span className="text-sm text-ink-400">{progress.data.overall_percent}% overall</span>}>
        {tracks.error && <ErrorBox error={tracks.error} />}
        <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
          {tracks.data?.map((t) => (
            <div key={t.id}>
              <div className="mb-1.5 flex justify-between text-sm">
                <span className={t.status === "available" ? "text-white" : "text-ink-400"}>{t.name}</span>
                <span className="tabular-nums text-ink-400">
                  {t.status === "planned" ? `Phase ${t.phase}` : `${t.progress.percent}%`}
                </span>
              </div>
              <Progress percent={t.progress.percent} label={`${t.name} progress`} />
            </div>
          ))}
        </div>
        {progress.data && (
          <div className="mt-5 flex flex-wrap gap-x-6 gap-y-1 border-t border-ink-700 pt-3 text-xs text-ink-400">
            <span>{progress.data.modules_completed}/{progress.data.modules_total} modules</span>
            <span>{progress.data.challenges_passed} challenges passed · {progress.data.challenges_failed} failed</span>
            <span>{progress.data.hints_used} hints used</span>
            <span>{duration(progress.data.learning_seconds)} in labs</span>
          </div>
        )}
      </Card>

      <div className="grid gap-6">
        <Card title="Recently accessed">
          {activity.error ? <ErrorBox error={activity.error} /> : activity.data?.length ? (
            <ul className="space-y-2">{activity.data.map((a) => (
              <li key={`${a.kind}-${a.ref_id}`} className="flex justify-between gap-3 text-sm">
                <span className="truncate text-ink-200">{a.title}</span>
                <span className="shrink-0 text-xs text-ink-400">{ago(a.at)}</span>
              </li>))}
            </ul>
          ) : <Empty>Nothing yet. Modules and projects you open show up here.</Empty>}
        </Card>
        <Card title="Recent challenges">
          {attempts.error ? <ErrorBox error={attempts.error} /> : attempts.data?.length ? (
            <ul className="space-y-2">{attempts.data.map((a) => (
              <li key={a.id} className="flex justify-between gap-3 text-sm">
                <span className="truncate">{a.name}</span><Badge>{a.status}</Badge>
              </li>))}
            </ul>
          ) : <Empty>No challenges attempted. The troubleshooting engine arrives in Phase 6.</Empty>}
        </Card>
      </div>
    </div>
  );
}
