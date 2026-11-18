import { useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { KeyRound } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../lib/auth";
import { Code } from "../components/ui";

export default function Login() {
  const { me, refresh } = useAuth();
  const [token, setToken] = useState("");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const submit = async (value: string) => {
    setBusy(true);
    setError(undefined);
    try {
      await api.login(value);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // The backend prints a link with #token=…; the fragment never reaches any server log.
  useEffect(() => {
    const fromHash = () => {
      const t = new URLSearchParams(window.location.hash.slice(1)).get("token");
      if (t) {
        window.history.replaceState(null, "", window.location.pathname);
        void submit(t);
      }
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    return () => window.removeEventListener("hashchange", fromHash);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (me) return <Navigate to="/" replace />;
  const onSubmit = (e: FormEvent) => { e.preventDefault(); void submit(token.trim()); };

  return (
    <div className="flex min-h-full items-center justify-center p-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm rounded-xl border border-ink-700 bg-ink-900 p-6">
        <div className="text-xl font-bold text-white">DevOps<span className="text-accent">Lab</span></div>
        <p className="mt-1 text-sm text-ink-400">Learn. Build. Break. Troubleshoot. Master.</p>
        <label htmlFor="token" className="mt-6 block text-sm font-medium text-ink-200">Login token</label>
        <input id="token" type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)}
          className="mt-1.5 w-full rounded-md border border-ink-700 bg-ink-950 px-3 py-2 font-mono text-sm text-white outline-none focus:border-accent" />
        <p className="mt-2 text-xs text-ink-400">Run <Code>make token</Code> in the devopslab folder to see it.</p>
        {error && <p role="alert" className="mt-3 text-sm text-bad">{error}</p>}
        <button type="submit" disabled={busy || !token.trim()}
          className="mt-5 flex w-full items-center justify-center gap-2 rounded-md bg-accent px-4 py-2 font-semibold text-ink-950 disabled:opacity-50">
          <KeyRound className="h-4 w-4" />{busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
