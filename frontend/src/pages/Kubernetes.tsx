import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "../api";
import { useApi } from "../lib/useApi";
import { age } from "../lib/format";
import { Card, ClusterDown, ErrorBox, PageHeader, PlannedBadge } from "../components/ui";

const statusColor = (s: string) =>
  s === "Running" || s === "Succeeded" || s === "Completed" ? "text-ok" : s === "Pending" || s === "ContainerCreating" ? "text-warn" : "text-bad";

export default function Kubernetes() {
  const cluster = useApi(api.cluster, 10_000);
  const pods = useApi(() => api.pods(), 10_000);
  const [ns, setNs] = useState("all");
  const c = cluster.data;
  const namespaces = [...new Set(pods.data?.map((p) => p.namespace))].sort();
  const shown = pods.data?.filter((p) => ns === "all" || p.namespace === ns);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title="Kubernetes" subtitle="Live view of the lab cluster.">
        <span className="text-xs text-ink-400">Deployments, services, logs and events: <PlannedBadge phase={3} /></span>
      </PageHeader>
      {cluster.error && <ErrorBox error={cluster.error} />}
      {c && !c.connected ? <ClusterDown reason={c.reason} /> : (
        <>
          <Card title="Nodes">
            <div className="grid gap-3 sm:grid-cols-3">
              {c?.nodes?.items.map((n) => (
                <div key={n.name} className="rounded-lg bg-ink-800 p-3">
                  <div className="truncate font-mono text-sm text-white">{n.name}</div>
                  <div className="mt-1 flex justify-between text-xs text-ink-400">
                    <span>{n.roles.join(", ")} · {n.version} · {n.arch}</span>
                    <span className={n.ready ? "text-ok" : "text-bad"}>{n.ready ? "Ready" : "NotReady"}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
          <Card title={`Pods${shown ? ` (${shown.length})` : ""}`}
            action={
              <div className="flex items-center gap-2">
                <select value={ns} onChange={(e) => setNs(e.target.value)} aria-label="Namespace"
                  className="rounded-md border border-ink-700 bg-ink-800 px-2 py-1 text-sm">
                  <option value="all">All namespaces</option>
                  {namespaces.map((n) => <option key={n}>{n}</option>)}
                </select>
                <button onClick={() => void pods.reload()} className="rounded-md p-1.5 text-ink-400 hover:bg-ink-800" aria-label="Refresh pods">
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>
            }>
            {pods.error && <ErrorBox error={pods.error} title="Couldn't list pods" />}
            <div className="overflow-x-auto">
              <table className="w-full font-mono text-sm">
                <thead className="text-left text-xs uppercase text-ink-400">
                  <tr>{["Namespace", "Name", "Ready", "Status", "Restarts", "Age", "Node"].map((h) => <th key={h} className="py-2 pr-4 font-medium">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-ink-800">
                  {shown?.map((p) => (
                    <tr key={`${p.namespace}/${p.name}`}>
                      <td className="py-1.5 pr-4 text-ink-400">{p.namespace}</td>
                      <td className="py-1.5 pr-4 text-white">{p.name}</td>
                      <td className="py-1.5 pr-4">{p.ready}</td>
                      <td className={`py-1.5 pr-4 ${statusColor(p.status)}`}>{p.status}</td>
                      <td className="py-1.5 pr-4 tabular-nums">{p.restarts}</td>
                      <td className="py-1.5 pr-4 tabular-nums text-ink-400">{age(p.age_seconds)}</td>
                      <td className="py-1.5 pr-4 text-ink-400">{p.node ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
