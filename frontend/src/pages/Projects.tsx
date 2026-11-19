import { api } from "../api";
import { ProjectLab } from "../components/ProjectLab";
import { useApi } from "../lib/useApi";
import { Card, ErrorBox, PageHeader, PlannedBadge } from "../components/ui";

export default function Projects() {
  const { data, error } = useApi(api.projects);
  const labs = useApi(api.labs);
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Projects" subtitle="Engineer Mode: production-style projects you deploy on demand, explore, break and restore." />
      {error && <ErrorBox error={error} />}
      <div className="grid gap-6 md:grid-cols-2">
        {data?.map((p) => (
          <Card key={p.id} title={p.name} action={p.status === "planned" && <PlannedBadge phase={p.phase} />}>
            <p className="text-sm text-ink-200">{p.summary}</p>
            <h3 className="mt-4 text-xs font-medium uppercase tracking-wider text-ink-400">Components</h3>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {p.components.map((c) => <span key={c} className="rounded bg-ink-800 px-2 py-0.5 text-xs text-ink-200">{c}</span>)}
            </div>
            <h3 className="mt-4 text-xs font-medium uppercase tracking-wider text-ink-400">You'll practise</h3>
            <p className="mt-1 text-sm text-ink-400">{p.topics.join(" · ")}</p>
            {p.lab && p.status === "available" && (
              <div className="mt-4">
                {labs.error ? <ErrorBox error={labs.error} title="Couldn't load lab status" />
                  : labs.data ? <ProjectLab labId={p.lab} initial={labs.data.find((l) => l.id === p.lab)} />
                  : <p className="text-sm text-ink-400">Loading lab…</p>}
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
