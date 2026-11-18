import { useEffect, useState } from "react";
import { Box, Loader2, Lock, Plus, SquareTerminal, Terminal as TermIcon, X } from "lucide-react";
import { api, type TerminalProfile, type TerminalProfileId, type TerminalSession } from "../api";
import { Card, ErrorBox, PageHeader, PlannedBadge } from "../components/ui";
import { TerminalView } from "../components/terminal/TerminalView";

const ICON: Record<TerminalProfileId, typeof TermIcon> = { linux: TermIcon, kubernetes: Box, docker: SquareTerminal };
const LABEL: Record<TerminalProfileId, string> = { linux: "Linux", kubernetes: "Kubernetes", docker: "Docker" };

export default function TerminalPage() {
  const [profiles, setProfiles] = useState<TerminalProfile[]>([]);
  const [sessions, setSessions] = useState<TerminalSession[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [starting, setStarting] = useState<TerminalProfileId | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    Promise.all([api.terminalProfiles(), api.terminalSessions()])
      .then(([p, s]) => { setProfiles(p); setSessions(s); setActive(s[0]?.id ?? null); })
      .catch(setError)
      .finally(() => setLoaded(true));
  }, []);

  const open = async (profile: TerminalProfileId) => {
    setStarting(profile);
    setError(null);
    try {
      const s = await api.openTerminal(profile);
      setSessions((xs) => [...xs, s]);
      setActive(s.id);
    } catch (e) {
      setError(e as Error);
    } finally {
      setStarting(null);
    }
  };

  const close = async (id: string) => {
    try {
      await api.closeTerminal(id);
    } catch (e) {
      setError(e as Error);
      return;
    }
    const rest = sessions.filter((x) => x.id !== id);
    setSessions(rest);
    if (active === id) setActive(rest[rest.length - 1]?.id ?? null);
  };

  const counts: Record<string, number> = {};
  const tabName = (s: TerminalSession) => {
    counts[s.profile] = (counts[s.profile] ?? 0) + 1;
    return `${LABEL[s.profile]} ${counts[s.profile]}`;
  };

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col">
      <PageHeader title="Terminal" subtitle="Real shells in disposable sandbox pods inside the lab cluster, never on your Mac.">
        <div className="flex flex-wrap gap-2">
          {profiles.map((p) => {
            const Icon = ICON[p.id];
            return p.available ? (
              <button key={p.id} onClick={() => open(p.id)} disabled={starting !== null} title={p.description}
                className="inline-flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-900 px-3 py-1.5 text-sm text-ink-200 hover:border-accent hover:text-white disabled:opacity-50">
                {starting === p.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                <Icon className="h-4 w-4" />{p.name}
              </button>
            ) : (
              <span key={p.id} title={p.description}
                className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-ink-700 px-3 py-1.5 text-sm text-ink-400">
                <Icon className="h-4 w-4" />{p.name} <PlannedBadge phase={p.phase ?? 2} label="Planned" />
              </span>
            );
          })}
        </div>
      </PageHeader>

      {error && <div className="mb-4"><ErrorBox error={error} title="Terminal error" /></div>}
      {starting && (
        <p className="mb-3 text-sm text-ink-400" role="status">
          Starting a {LABEL[starting]} sandbox pod… (usually a few seconds; the first start after <code>make up</code> can take longer)
        </p>
      )}

      {sessions.length > 0 ? (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-ink-700 bg-ink-900">
          <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-ink-700 px-2 pt-2">
            {sessions.map((s) => (
              <div key={s.id} role="tab" aria-selected={active === s.id}
                className={`group flex items-center gap-2 rounded-t-md px-3 py-1.5 text-sm ${active === s.id ? "bg-ink-800 text-white" : "text-ink-400 hover:text-ink-200"}`}>
                <button onClick={() => setActive(s.id)}>{tabName(s)}</button>
                <button aria-label={`Close ${LABEL[s.profile]} terminal`} onClick={() => close(s.id)}
                  className="rounded p-0.5 hover:bg-ink-700"><X className="h-3.5 w-3.5" /></button>
              </div>
            ))}
          </div>
          <div className="min-h-0 flex-1">
            {sessions.map((s) => (
              <TerminalView key={s.id} session={s} active={active === s.id} onClose={() => close(s.id)} />
            ))}
          </div>
        </div>
      ) : loaded && (
        <Card title="Security boundaries">
          <p className="mb-3 text-sm text-ink-300">Open a terminal above. Each one is its own sandbox pod:</p>
          <ul className="space-y-2 text-sm text-ink-200">
            {["Runs in the lab cluster, never on your Mac. No host Docker socket or host files.",
              "Non-root, all capabilities dropped, read-only root filesystem, CPU and memory limits.",
              "Linux: no cluster access and no network. Kubernetes: kubectl scoped to the lab-playground namespace, read-only elsewhere, never cluster-admin.",
              "Needs your login. Idle sessions close after 30 minutes and every session ends after 4 hours."].map((t) => (
              <li key={t} className="flex gap-2"><Lock className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" />{t}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
