import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Circle, Clock, ExternalLink, Loader2, Play, RotateCcw, Rocket, Square, Trash2, XCircle } from "lucide-react";
import { api, type Lab, type LabStep, type LabUsage } from "../api";
import { Badge } from "./ui";

const BUSY = new Set(["deploying", "starting", "stopping", "resetting", "deleting"]);
const btn = "inline-flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-900 px-3 py-1.5 text-sm text-ink-200 hover:border-accent hover:text-white disabled:opacity-50";

type Confirm = "reset" | "delete" | null;
const CONFIRM_TEXT = {
  reset: "Reset deletes the lab namespace, including its database, and deploys it again from the known-good manifests.",
  delete: "Delete removes the lab namespace and everything in it, including the database.",
};

function StepRow({ s }: { s: LabStep }) {
  const icon = {
    ok: <CheckCircle2 className="h-4 w-4 text-ok" />, failed: <XCircle className="h-4 w-4 text-bad" />,
    running: <Loader2 className="h-4 w-4 animate-spin text-accent" />, pending: <Circle className="h-4 w-4 text-ink-700" />,
  }[s.state];
  return (
    <li className="text-sm" data-state={s.state}>
      <div className="flex items-center gap-2">
        {icon}
        <span className={s.state === "pending" ? "text-ink-400" : "text-white"}>{s.name}</span>
        {s.seconds != null && <span className="text-xs tabular-nums text-ink-400">{s.seconds}s</span>}
        {s.state === "ok" && s.detail && <span className="truncate text-xs text-ink-400">{s.detail}</span>}
      </div>
      {s.state === "failed" && s.detail && (
        <pre className="ml-6 mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-ink-950 p-2 font-mono text-xs text-bad">{s.detail}</pre>
      )}
    </li>
  );
}

function timeLeft(iso: string, now: number) {
  const ms = new Date(iso).getTime() - now;
  if (ms <= 0) return "stopping soon";
  const m = Math.round(ms / 60_000);
  return m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m left` : `${m}m left`;
}

function Usage({ id }: { id: string }) {
  const [u, setU] = useState<LabUsage | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const load = () => api.labUsage(id).then((x) => { setU(x); setErr(null); }).catch((e: Error) => setErr(e.message));
    void load();
    const t = setInterval(load, 15_000);
    return () => clearInterval(t);
  }, [id]);
  if (err) return <p className="text-xs text-bad">Usage unavailable: {err}</p>;
  if (!u) return null;
  const q = (k: string) => (u.quota[k] ? `${u.quota[k].used} / ${u.quota[k].hard}` : "–");
  return (
    <div aria-label="Lab usage" className="grid grid-cols-2 gap-x-6 gap-y-1 rounded-lg bg-ink-800/60 p-3 text-xs sm:grid-cols-4">
      <div><div className="text-ink-400">CPU now</div><div className="tabular-nums text-white">{u.metrics_error ? "–" : `${u.cpu_millicores}m`}</div></div>
      <div><div className="text-ink-400">Memory now</div><div className="tabular-nums text-white">{u.metrics_error ? "–" : `${u.memory_mib} MiB`}</div></div>
      <div><div className="text-ink-400">Pods (quota)</div><div className="tabular-nums text-white">{q("pods")}</div></div>
      <div><div className="text-ink-400">Memory limits (quota)</div><div className="tabular-nums text-white">{q("limits.memory")}</div></div>
      {u.metrics_error && <p className="col-span-full text-ink-400">{u.metrics_error}</p>}
    </div>
  );
}

/** Deploy and manage one project's lab. Every state shown comes from the API; failures show the failing step. */
export function ProjectLab({ labId, initial }: { labId: string; initial?: Lab }) {
  const [lab, setLab] = useState<Lab | undefined>(initial);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [now, setNow] = useState(() => Date.now());
  const busy = !!lab && (BUSY.has(lab.status) || lab.operation?.state === "running");

  const refresh = useCallback(async () => {
    try { setLab(await api.lab(labId)); } catch (e) { setError((e as Error).message); }
  }, [labId]);

  useEffect(() => { if (!initial) void refresh(); }, [initial, refresh]);
  useEffect(() => {
    const t = setInterval(() => { setNow(Date.now()); void refresh(); }, busy ? 2000 : 30_000);
    return () => clearInterval(t);
  }, [busy, refresh]);

  const run = async (fn: () => Promise<Lab>) => {
    setError(null);
    setConfirm(null);
    try { setLab(await fn()); } catch (e) { setError((e as Error).message); }
  };

  if (!lab) return error ? <p className="text-sm text-bad">{error}</p> : <p className="text-sm text-ink-400">Loading lab…</p>;
  const s = lab.status;
  const op = lab.operation;
  const showSteps = op && (op.state === "running" || op.state === "failed" || Date.now() / 1000 - (op.finished_at ?? 0) < 60);

  return (
    <section aria-label={`${lab.ref_id} lab`} className="space-y-3 border-t border-ink-800 pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium uppercase tracking-wider text-ink-400">Lab</span>
        <Badge tone={BUSY.has(s) ? "started" : s}>{s.replace("_", " ")}</Badge>
        {lab.namespaces.length > 0 && <span className="font-mono text-xs text-ink-400">{lab.namespaces.join(", ")}</span>}
        {s === "running" && lab.expires_at && (
          <span className="flex items-center gap-1 text-xs text-ink-400" title={`Stops at ${new Date(lab.expires_at).toLocaleTimeString()}`}>
            <Clock className="h-3.5 w-3.5" />{timeLeft(lab.expires_at, now)}
          </span>
        )}
      </div>

      {!busy && !confirm && (
        <div className="flex flex-wrap gap-2">
          {s === "not_deployed" && <button className={btn} onClick={() => run(() => api.deployLab(lab.ref_id))}><Rocket className="h-4 w-4" />Deploy</button>}
          {s === "running" && lab.url && (
            <a className={btn} href={lab.url} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" />Open {lab.url.replace(/^https?:\/\//, "")}</a>
          )}
          {(s === "stopped" || s === "failed") && <button className={btn} onClick={() => run(() => api.labDo(lab.id, "start"))}><Play className="h-4 w-4" />Start</button>}
          {(s === "running" || s === "failed") && <button className={btn} onClick={() => run(() => api.labDo(lab.id, "stop"))}><Square className="h-4 w-4" />Stop</button>}
          {s === "running" && <button className={btn} onClick={() => run(() => api.labDo(lab.id, "extend"))}><Clock className="h-4 w-4" />Extend time</button>}
          {s !== "not_deployed" && <button className={btn} onClick={() => setConfirm("reset")}><RotateCcw className="h-4 w-4" />Reset</button>}
          {s !== "not_deployed" && <button className={btn} onClick={() => setConfirm("delete")}><Trash2 className="h-4 w-4" />Delete</button>}
        </div>
      )}
      {confirm && (
        <div role="alertdialog" aria-label={`Confirm ${confirm}`} className="space-y-2 rounded-lg border border-warn/40 bg-warn/10 p-3 text-sm text-ink-200">
          <p>{CONFIRM_TEXT[confirm]}</p>
          <div className="flex gap-2">
            <button className={btn} onClick={() => run(() => (confirm === "reset" ? api.labDo(lab.id, "reset") : api.deleteLab(lab.id)))}>
              {confirm === "reset" ? "Reset lab" : "Delete lab"}
            </button>
            <button className="text-ink-400 hover:text-white" onClick={() => setConfirm(null)}>Cancel</button>
          </div>
        </div>
      )}

      {error && <p role="alert" className="text-sm text-bad">{error}</p>}
      {s === "failed" && lab.last_error && !(op?.state === "failed") && (
        <div role="alert" className="rounded-lg border border-bad/40 bg-bad/10 p-3 text-sm">
          <div className="font-medium text-bad">The last operation failed</div>
          <pre className="mt-1 whitespace-pre-wrap font-mono text-xs text-ink-200">{lab.last_error}</pre>
        </div>
      )}
      {showSteps && op && (
        <div aria-label="Lab steps">
          <div className={`mb-1 text-xs ${op.state === "failed" ? "text-bad" : op.state === "succeeded" ? "text-ok" : "text-ink-400"}`}>
            {op.action}: {op.state === "running" ? "in progress…" : op.state === "failed" ? `failed at “${op.failed_step}”` : "done"}
          </div>
          <ol className="space-y-1">{op.steps.map((st) => <StepRow key={st.name} s={st} />)}</ol>
        </div>
      )}
      {s === "running" && <Usage id={lab.id} />}
    </section>
  );
}
