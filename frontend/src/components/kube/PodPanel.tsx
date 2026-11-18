import { useEffect, useRef, useState } from "react";
import { FileCode2, Radio, ScrollText, X } from "lucide-react";
import { api, followLogs, type PodDetail } from "../../api";
import { age } from "../../lib/format";
import { ErrorBox } from "../ui";

type Tab = "overview" | "logs" | "yaml";

export function PodPanel({ namespace, name, onClose }: { namespace: string; name: string; onClose: () => void }) {
  const [pod, setPod] = useState<PodDetail | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  useEffect(() => {
    setPod(null); setError(null); setTab("overview");
    api.pod(namespace, name).then(setPod).catch(setError);
  }, [namespace, name]);

  const tabBtn = (t: Tab, label: string, Icon: typeof X) => (
    <button role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
      className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm ${tab === t ? "bg-ink-800 text-white" : "text-ink-400 hover:text-ink-200"}`}>
      <Icon className="h-4 w-4" />{label}
    </button>
  );

  return (
    <aside aria-label={`Pod ${name}`} className="rounded-xl border border-ink-700 bg-ink-900">
      <header className="flex flex-wrap items-center gap-2 border-b border-ink-700 px-4 py-3">
        <div className="min-w-0 flex-1">
          <div className="truncate font-mono text-sm text-white">{name}</div>
          <div className="text-xs text-ink-400">{namespace}{pod ? ` · ${pod.phase} · ${pod.node ?? "unscheduled"} · ${pod.pod_ip ?? "no IP"}` : ""}</div>
        </div>
        <div role="tablist" className="flex gap-1">
          {tabBtn("overview", "Overview", ScrollText)}{tabBtn("logs", "Logs", Radio)}{tabBtn("yaml", "YAML", FileCode2)}
        </div>
        <button aria-label="Close pod details" onClick={onClose} className="rounded p-1 text-ink-400 hover:bg-ink-800"><X className="h-4 w-4" /></button>
      </header>
      <div className="p-4">
        {error && <ErrorBox error={error} title="Couldn't load the pod" />}
        {pod && tab === "overview" && <Overview pod={pod} />}
        {pod && tab === "logs" && <Logs pod={pod} />}
        {tab === "yaml" && <YamlView kind="pod" namespace={namespace} name={name} />}
      </div>
    </aside>
  );
}

function Overview({ pod }: { pod: PodDetail }) {
  return (
    <div className="space-y-4 text-sm">
      <div className="grid gap-3 md:grid-cols-2">
        {pod.containers.map((c) => (
          <div key={c.name} className="rounded-lg bg-ink-800 p-3">
            <div className="flex justify-between gap-2">
              <span className="font-mono text-white">{c.name}</span>
              <span className={c.ready ? "text-ok" : c.state === "Running" ? "text-warn" : "text-bad"}>{c.state}</span>
            </div>
            <div className="mt-1 break-all font-mono text-xs text-ink-400">{c.image}</div>
            {c.state_detail && <div className="mt-1 text-xs text-ink-300">{c.state_detail}</div>}
            <div className="mt-2 text-xs text-ink-400">
              Restarts {c.restarts}
              {c.last_state && <> · last: <span className="text-ink-200">{c.last_state}</span>{c.last_state_detail ? ` (${c.last_state_detail})` : ""}</>}
              {c.ports.length > 0 && <> · ports {c.ports.join(", ")}</>}
            </div>
          </div>
        ))}
      </div>
      <div>
        <h3 className="mb-1 text-xs uppercase text-ink-400">Conditions</h3>
        <div className="flex flex-wrap gap-2">
          {pod.conditions.map((c) => (
            <span key={c.type} title={c.message ?? c.reason ?? ""} className={`rounded px-2 py-0.5 text-xs ${c.status === "True" ? "bg-ok/15 text-ok" : "bg-bad/15 text-bad"}`}>
              {c.type}{c.reason ? `: ${c.reason}` : ""}
            </span>
          ))}
        </div>
      </div>
      <div>
        <h3 className="mb-1 text-xs uppercase text-ink-400">Events</h3>
        {pod.events.length === 0 ? <p className="text-xs text-ink-400">No recent events (Kubernetes keeps them for about an hour).</p> : (
          <ul className="space-y-1 font-mono text-xs">
            {pod.events.map((e, i) => (
              <li key={i} className={e.type === "Warning" ? "text-amber-200" : "text-ink-300"}>
                <span className="text-ink-400">{age(e.last_seen_seconds)}</span> {e.reason}{e.count > 1 ? ` (x${e.count})` : ""}: {e.message}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Logs({ pod }: { pod: PodDetail }) {
  const [container, setContainer] = useState(pod.containers[0]?.name ?? "");
  const [previous, setPrevious] = useState(false);
  const [lines, setLines] = useState<string[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [following, setFollowing] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const box = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (following) return;
    setError(null);
    api.logs(pod.namespace, pod.name, container, 500, previous)
      .then((t) => setLines(t ? t.replace(/\n$/, "").split("\n") : []))
      .catch(setError);
  }, [pod.namespace, pod.name, container, previous, following]);

  useEffect(() => {
    if (!following) return;
    setLines([]); setNote(null);
    return followLogs(pod.namespace, pod.name, container,
      (l) => setLines((xs) => (xs.length > 2000 ? [...xs.slice(-1500), l] : [...xs, l])),
      (reason) => { setNote(reason); setFollowing(false); });
  }, [following, pod.namespace, pod.name, container]);

  useEffect(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight; }, [lines]);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {pod.containers.length > 1 && (
          <select aria-label="Container" value={container} onChange={(e) => setContainer(e.target.value)}
            className="rounded-md border border-ink-700 bg-ink-800 px-2 py-1">
            {pod.containers.map((c) => <option key={c.name}>{c.name}</option>)}
          </select>
        )}
        <label className="flex items-center gap-1.5 text-ink-300">
          <input type="checkbox" checked={following} onChange={(e) => { setPrevious(false); setFollowing(e.target.checked); }} />Follow live
        </label>
        <label className="flex items-center gap-1.5 text-ink-300">
          <input type="checkbox" checked={previous} disabled={following} onChange={(e) => setPrevious(e.target.checked)} />Previous container (after a crash)
        </label>
        {note && <span className="text-xs text-ink-400">{note}</span>}
      </div>
      {error && <ErrorBox error={error} title="Couldn't read logs" />}
      <pre ref={box} aria-label="Logs" className="h-96 overflow-auto rounded-lg bg-ink-950 p-3 font-mono text-xs text-ink-200">
        {lines.length ? lines.join("\n") : <span className="text-ink-400">{following ? "Waiting for new lines…" : "No log output."}</span>}
      </pre>
    </div>
  );
}

export function YamlView({ kind, namespace, name }: { kind: Parameters<typeof api.yaml>[0]; namespace?: string; name: string }) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    setText(null); setError(null);
    api.yaml(kind, name, namespace).then(setText).catch(setError);
  }, [kind, namespace, name]);
  if (error) return <ErrorBox error={error} title="Couldn't load YAML" />;
  return (
    <pre aria-label="YAML" className="max-h-[32rem] overflow-auto rounded-lg bg-ink-950 p-3 font-mono text-xs text-ink-200">
      {text ?? "Loading…"}
    </pre>
  );
}
