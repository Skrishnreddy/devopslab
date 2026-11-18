import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "../api";
import { useApi } from "../useApi";
import { Card, ClusterDown } from "../components/ui";

const statusColor = (s: string) =>
  s === "Running" || s === "Succeeded" ? "text-ok" : s === "Pending" ? "text-warn" : "text-bad";

export default function Kubernetes() {
  const { data: c } = useApi(api.cluster, 10_000);
  const { data: pods, error, reload } = useApi(api.pods, 10_000);
  const [ns, setNs] = useState("all");
  if (c && !c.connected) return <div className="mx-auto max-w-5xl"><ClusterDown reason={c.reason} /></div>;
  const namespaces = [...new Set(pods?.map((p) => p.namespace))].sort();
  const shown = pods?.filter((p) => ns === "all" || p.namespace === ns);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <Card title="Nodes">
        <div className="grid gap-3 sm:grid-cols-3">
          {c?.nodes?.items.map((n) => (
            <div key={n.name} className="rounded-lg bg-ink-800 p-3">
              <div className="truncate font-mono text-sm text-white">{n.name}</div>
              <div className="mt-1 flex justify-between text-xs text-ink-400">
                <span>{n.roles.join(", ")} · {n.version}</span>
                <span className={n.ready ? "text-ok" : "text-bad"}>{n.ready ? "Ready" : "NotReady"}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
      <Card
        title="Pods"
        action={
          <div className="flex items-center gap-2">
            <select value={ns} onChange={(e) => setNs(e.target.value)}
              className="rounded-md border border-ink-700 bg-ink-800 px-2 py-1 text-sm" aria-label="Namespace">
              <option value="all">All namespaces</option>
              {namespaces.map((n) => <option key={n}>{n}</option>)}
            </select>
            <button onClick={reload} className="rounded-md p-1.5 text-ink-400 hover:bg-ink-800" aria-label="Refresh">
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        }
      >
        {error && <p className="text-sm text-bad">{error}</p>}
        <div className="overflow-x-auto">
          <table className="w-full font-mono text-sm">
            <thead className="text-left text-xs uppercase text-ink-400">
              <tr>{["Namespace", "Name", "Ready", "Status", "Restarts", "Node"].map((h) => <th key={h} className="py-2 pr-4 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-ink-800">
              {shown?.map((p) => (
                <tr key={`${p.namespace}/${p.name}`}>
                  <td className="py-1.5 pr-4 text-ink-400">{p.namespace}</td>
                  <td className="py-1.5 pr-4 text-white">{p.name}</td>
                  <td className="py-1.5 pr-4">{p.ready}</td>
                  <td className={`py-1.5 pr-4 ${statusColor(p.status)}`}>{p.status}</td>
                  <td className="py-1.5 pr-4 tabular-nums">{p.restarts}</td>
                  <td className="py-1.5 pr-4 text-ink-400">{p.node}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
