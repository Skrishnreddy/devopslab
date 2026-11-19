import { useEffect, useState } from "react";
import { Loader2, Play, Square } from "lucide-react";
import { api, type LabOperation } from "../api";

/** Start/stop the lab with the same scripts as `make up` / `make down`, showing their real output. */
export function LabControls({ connected, onDone }: { connected: boolean; onDone?: () => void }) {
  const [op, setOp] = useState<LabOperation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmStop, setConfirmStop] = useState(false);
  const running = op?.state === "running";

  useEffect(() => { api.labOperation().then(setOp).catch(() => undefined); }, []);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(async () => {
      try {
        const next = await api.labOperation();
        setOp(next);
        if (next && next.state !== "running") onDone?.();
      } catch (e) { setError((e as Error).message); }
    }, 2000);
    return () => clearInterval(t);
  }, [running, onDone]);

  const run = async (action: "start" | "stop") => {
    setError(null);
    setConfirmStop(false);
    try { setOp(await api.labAction(action)); } catch (e) { setError((e as Error).message); }
  };

  const btn = "inline-flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-900 px-3 py-1.5 text-sm text-ink-200 hover:border-accent hover:text-white disabled:opacity-50";
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {!connected && (
          <button className={btn} disabled={running} onClick={() => run("start")}>
            {running && op?.action === "start" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}Start lab
          </button>
        )}
        {connected && !confirmStop && (
          <button className={btn} disabled={running} onClick={() => setConfirmStop(true)}>
            {running && op?.action === "stop" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}Stop lab
          </button>
        )}
        {confirmStop && (
          <span className="flex items-center gap-2 text-sm text-ink-300">
            Stop the VMs? Open terminals will close; the cluster is kept.
            <button className={btn} onClick={() => run("stop")}>Stop</button>
            <button className="text-ink-400 hover:text-white" onClick={() => setConfirmStop(false)}>Cancel</button>
          </span>
        )}
        {op && (
          <span role="status" className={`text-xs ${op.state === "failed" ? "text-bad" : op.state === "succeeded" ? "text-ok" : "text-ink-400"}`}>
            {op.action === "start" ? "make up" : "make down"}: {op.state === "running" ? "running…" : op.state}
            {op.state === "failed" && op.exit_code != null ? ` (exit ${op.exit_code})` : ""}
          </span>
        )}
      </div>
      {error && <p className="text-sm text-bad">{error}</p>}
      {op && (running || op.state === "failed") && op.output.length > 0 && (
        <pre aria-label="Lab output" className="max-h-56 overflow-auto rounded-lg bg-ink-950 p-3 font-mono text-xs text-ink-300">
          {op.output.slice(-40).join("\n")}
        </pre>
      )}
    </div>
  );
}
