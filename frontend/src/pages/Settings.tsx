import { useState } from "react";
import { LogOut } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/useApi";
import { Badge, Card, ErrorBox, PageHeader, PlannedBadge } from "../components/ui";

export default function Settings() {
  const { me, logout } = useAuth();
  const settings = useApi(api.settings);
  const features = useApi(api.features);
  const [error, setError] = useState<Error>();
  const doLogout = async () => { try { await logout(); } catch (e) { setError(e as Error); } };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader title="Settings" />
      {error && <ErrorBox error={error} title="Couldn't log out" />}
      <Card title="Account" action={
        <button onClick={doLogout} className="flex items-center gap-1.5 rounded-md border border-ink-700 px-3 py-1.5 text-sm hover:bg-ink-800">
          <LogOut className="h-4 w-4" /> Log out
        </button>}>
        {me && <dl className="grid grid-cols-[10rem_1fr] gap-y-2 text-sm">
          <dt className="text-ink-400">User</dt><dd className="text-white">{me.username} ({me.role})</dd>
          <dt className="text-ink-400">Session expires</dt><dd>{new Date(me.session_expires_at).toLocaleString()}</dd>
        </dl>}
      </Card>
      <Card title="Environment">
        {settings.error && <ErrorBox error={settings.error} />}
        {settings.data && <dl className="grid grid-cols-[10rem_1fr] gap-y-2 text-sm">
          {Object.entries(settings.data.environment).map(([k, v]) => (
            <div key={k} className="contents"><dt className="text-ink-400">{k.replace(/_/g, " ")}</dt><dd className="break-all font-mono">{v}</dd></div>
          ))}
        </dl>}
        <p className="mt-3 text-xs text-ink-400">Change these with DEVOPSLAB_* variables in backend/.env (see .env.example).</p>
      </Card>
      <Card title="AI assistant" action={<PlannedBadge phase={6} />}>
        <p className="text-sm text-ink-200">
          Optional. You'll choose a provider (Ollama locally, or your own API). Nothing from your terminal, code or
          cluster is sent to an external provider without asking you first.
        </p>
      </Card>
      <Card title="Features">
        {features.error && <ErrorBox error={features.error} />}
        <ul className="divide-y divide-ink-700">
          {features.data?.map((f) => (
            <li key={f.id} className="flex items-center justify-between py-2 text-sm">
              <span>{f.name}</span>
              {f.status === "available" ? <Badge>available</Badge> : <PlannedBadge phase={f.phase} />}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
