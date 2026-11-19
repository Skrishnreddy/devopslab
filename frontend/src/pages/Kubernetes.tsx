import { useEffect, useState, type ReactNode } from "react";
import { FileCode2, RefreshCw, X } from "lucide-react";
import { api, type YamlKind } from "../api";
import { useApi } from "../lib/useApi";
import { age } from "../lib/format";
import { Card, ClusterDown, ErrorBox, PageHeader } from "../components/ui";
import { LabControls } from "../components/LabControls";
import { PodPanel, YamlView } from "../components/kube/PodPanel";

type Tab = "pods" | "deployments" | "services" | "events" | "namespaces";
const TABS: Tab[] = ["pods", "deployments", "services", "events", "namespaces"];
const ok = (s: string) => s === "Running" || s === "Succeeded" || s === "Completed";
const statusColor = (s: string) => (ok(s) ? "text-ok" : s === "Pending" || s === "ContainerCreating" ? "text-warn" : "text-bad");

function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full font-mono text-sm">
        <thead className="text-left text-xs uppercase text-ink-400">
          <tr>{head.map((h) => <th key={h} className="py-2 pr-4 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-ink-800">{children}</tbody>
      </table>
    </div>
  );
}
const td = "py-1.5 pr-4";

export default function Kubernetes() {
  const cluster = useApi(api.cluster, 10_000);
  const c = cluster.data;
  const [ns, setNs] = useState("");
  const [tab, setTab] = useState<Tab>("pods");
  const [pod, setPod] = useState<{ namespace: string; name: string } | null>(null);
  const [yaml, setYaml] = useState<{ kind: YamlKind; namespace?: string; name: string } | null>(null);
  const connected = c?.connected === true;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title="Kubernetes" subtitle="Live, read-only view of the lab cluster. Same data as kubectl.">
        {c && <LabControls connected={connected} onDone={() => void cluster.reload()} />}
      </PageHeader>
      {cluster.error && <ErrorBox error={cluster.error} />}
      {c && !connected ? <ClusterDown reason={c.reason} /> : c && (
        <>
          <Card title="Nodes">
            <div className="grid gap-3 sm:grid-cols-3">
              {c.nodes?.items.map((n) => (
                <button key={n.name} onClick={() => setYaml({ kind: "node", name: n.name })}
                  className="rounded-lg bg-ink-800 p-3 text-left hover:ring-1 hover:ring-accent">
                  <div className="truncate font-mono text-sm text-white">{n.name}</div>
                  <div className="mt-1 flex justify-between text-xs text-ink-400">
                    <span>{n.roles.join(", ")} · {n.version} · {n.arch}</span>
                    <span className={n.ready ? "text-ok" : "text-bad"}>{n.ready ? "Ready" : "NotReady"}</span>
                  </div>
                </button>
              ))}
            </div>
          </Card>

          <div className="flex flex-wrap items-center gap-2">
            <div role="tablist" className="flex flex-wrap gap-1 rounded-lg bg-ink-900 p-1">
              {TABS.map((t) => (
                <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
                  className={`rounded-md px-3 py-1.5 text-sm capitalize ${tab === t ? "bg-ink-700 text-white" : "text-ink-400 hover:text-ink-200"}`}>{t}</button>
              ))}
            </div>
            {tab !== "namespaces" && <NamespacePicker value={ns} onChange={setNs} />}
          </div>

          {yaml && (
            <Card title={`${yaml.kind} ${yaml.namespace ? `${yaml.namespace}/` : ""}${yaml.name}`}
              action={<button aria-label="Close YAML" onClick={() => setYaml(null)} className="rounded p-1 text-ink-400 hover:bg-ink-800"><X className="h-4 w-4" /></button>}>
              <YamlView {...yaml} />
            </Card>
          )}
          {pod && <PodPanel {...pod} onClose={() => setPod(null)} />}

          {tab === "pods" && <Pods ns={ns} onOpen={setPod} />}
          {tab === "deployments" && <Deployments ns={ns} onYaml={setYaml} />}
          {tab === "services" && <Services ns={ns} onYaml={setYaml} />}
          {tab === "events" && <Events ns={ns} />}
          {tab === "namespaces" && <Namespaces onPick={(n) => { setNs(n); setTab("pods"); }} />}
        </>
      )}
    </div>
  );
}

function NamespacePicker({ value, onChange }: { value: string; onChange: (ns: string) => void }) {
  const nss = useApi(api.namespaces, 30_000);
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label="Namespace"
      className="rounded-md border border-ink-700 bg-ink-800 px-2 py-1.5 text-sm">
      <option value="">All namespaces</option>
      {nss.data?.map((n) => <option key={n.name} value={n.name}>{n.name}{n.lab ? " (lab)" : ""}</option>)}
    </select>
  );
}

/** Polls a namespaced list and reloads when the namespace changes. */
function useList<T>(fn: (ns?: string) => Promise<T>, ns: string) {
  const r = useApi(() => fn(ns || undefined), 10_000);
  const { reload } = r;
  useEffect(() => { void reload(); }, [ns, reload]);
  return r;
}

function ListCard({ title, count, error, reload, children }: {
  title: string; count?: number; error?: Error; reload: () => void; children: ReactNode;
}) {
  return (
    <Card title={`${title}${count != null ? ` (${count})` : ""}`}
      action={<button onClick={reload} className="rounded-md p-1.5 text-ink-400 hover:bg-ink-800" aria-label={`Refresh ${title.toLowerCase()}`}><RefreshCw className="h-4 w-4" /></button>}>
      {error && <ErrorBox error={error} title={`Couldn't list ${title.toLowerCase()}`} />}
      {children}
    </Card>
  );
}

const yamlBtn = (onClick: () => void, label: string) => (
  <button onClick={onClick} aria-label={label} title="YAML" className="rounded p-1 text-ink-400 hover:bg-ink-800 hover:text-white"><FileCode2 className="h-4 w-4" /></button>
);

function Pods({ ns, onOpen }: { ns: string; onOpen: (p: { namespace: string; name: string }) => void }) {
  const r = useList(api.pods, ns);
  return (
    <ListCard title="Pods" count={r.data?.length} error={r.error} reload={() => void r.reload()}>
      <Table head={["Namespace", "Name", "Ready", "Status", "Restarts", "Age", "Node"]}>
        {r.data?.map((p) => (
          <tr key={`${p.namespace}/${p.name}`} className="cursor-pointer hover:bg-ink-800/50" onClick={() => onOpen(p)}>
            <td className={`${td} text-ink-400`}>{p.namespace}</td>
            <td className={`${td} text-white underline-offset-2 hover:underline`}>{p.name}</td>
            <td className={td}>{p.ready}</td>
            <td className={`${td} ${statusColor(p.status)}`}>{p.status}</td>
            <td className={`${td} tabular-nums`}>{p.restarts}</td>
            <td className={`${td} tabular-nums text-ink-400`}>{age(p.age_seconds)}</td>
            <td className={`${td} text-ink-400`}>{p.node ?? "-"}</td>
          </tr>
        ))}
      </Table>
    </ListCard>
  );
}

type YamlOpen = (y: { kind: YamlKind; namespace?: string; name: string }) => void;

function Deployments({ ns, onYaml }: { ns: string; onYaml: YamlOpen }) {
  const r = useList(api.deployments, ns);
  return (
    <ListCard title="Deployments" count={r.data?.length} error={r.error} reload={() => void r.reload()}>
      <Table head={["Namespace", "Name", "Ready", "Up-to-date", "Available", "Age", "Images", ""]}>
        {r.data?.map((d) => (
          <tr key={`${d.namespace}/${d.name}`}>
            <td className={`${td} text-ink-400`}>{d.namespace}</td>
            <td className={`${td} text-white`}>{d.name}</td>
            <td className={`${td} ${d.healthy ? "text-ok" : "text-warn"}`}>{d.ready}</td>
            <td className={td}>{d.up_to_date}</td>
            <td className={td}>{d.available}</td>
            <td className={`${td} text-ink-400`}>{age(d.age_seconds)}</td>
            <td className={`${td} max-w-xs truncate text-xs text-ink-400`} title={d.images.join(", ")}>{d.images.join(", ")}</td>
            <td className={td}>{yamlBtn(() => onYaml({ kind: "deployment", namespace: d.namespace, name: d.name }), `YAML for deployment ${d.name}`)}</td>
          </tr>
        ))}
      </Table>
    </ListCard>
  );
}

function Services({ ns, onYaml }: { ns: string; onYaml: YamlOpen }) {
  const r = useList(api.services, ns);
  return (
    <ListCard title="Services" count={r.data?.length} error={r.error} reload={() => void r.reload()}>
      <Table head={["Namespace", "Name", "Type", "Cluster-IP", "External-IP", "Ports", "Selector", "Age", ""]}>
        {r.data?.map((s) => (
          <tr key={`${s.namespace}/${s.name}`}>
            <td className={`${td} text-ink-400`}>{s.namespace}</td>
            <td className={`${td} text-white`}>{s.name}</td>
            <td className={td}>{s.type}</td>
            <td className={td}>{s.cluster_ip ?? "-"}</td>
            <td className={td}>{s.external_ip ?? "<none>"}</td>
            <td className={td}>{s.ports}</td>
            <td className={`${td} text-xs text-ink-400`}>{Object.entries(s.selector).map(([k, v]) => `${k}=${v}`).join(",") || "<none>"}</td>
            <td className={`${td} text-ink-400`}>{age(s.age_seconds)}</td>
            <td className={td}>{yamlBtn(() => onYaml({ kind: "service", namespace: s.namespace, name: s.name }), `YAML for service ${s.name}`)}</td>
          </tr>
        ))}
      </Table>
    </ListCard>
  );
}

function Events({ ns }: { ns: string }) {
  const r = useList(api.events, ns);
  return (
    <ListCard title="Events" count={r.data?.length} error={r.error} reload={() => void r.reload()}>
      <Table head={["Last seen", "Type", "Reason", "Object", "Message"]}>
        {r.data?.map((e, i) => (
          <tr key={i}>
            <td className={`${td} whitespace-nowrap text-ink-400`}>{age(e.last_seen_seconds)}{e.count > 1 ? ` (x${e.count})` : ""}</td>
            <td className={`${td} ${e.type === "Warning" ? "text-warn" : "text-ink-300"}`}>{e.type}</td>
            <td className={td}>{e.reason}</td>
            <td className={`${td} text-ink-400`}>{e.namespace}/{e.object}</td>
            <td className={`${td} font-sans text-xs text-ink-200`}>{e.message}</td>
          </tr>
        ))}
      </Table>
      {r.data?.length === 0 && <p className="mt-2 text-sm text-ink-400">No events. Kubernetes keeps events for about an hour.</p>}
    </ListCard>
  );
}

function Namespaces({ onPick }: { onPick: (ns: string) => void }) {
  const r = useApi(api.namespaces, 30_000);
  return (
    <ListCard title="Namespaces" count={r.data?.length} error={r.error} reload={() => void r.reload()}>
      <Table head={["Name", "Status", "Age", ""]}>
        {r.data?.map((n) => (
          <tr key={n.name} className="cursor-pointer hover:bg-ink-800/50" onClick={() => onPick(n.name)}>
            <td className={`${td} text-white`}>{n.name}</td>
            <td className={td}>{n.status}</td>
            <td className={`${td} text-ink-400`}>{age(n.age_seconds)}</td>
            <td className={`${td} font-sans text-xs text-ink-400`}>{n.lab ? "lab namespace (resettable)" : n.managed ? "DevOpsLab system" : ""}</td>
          </tr>
        ))}
      </Table>
    </ListCard>
  );
}
