import { AlertTriangle } from "lucide-react";
import { api } from "../api";
import { useApi } from "../useApi";
import { Badge, Card } from "../components/ui";

export default function Engineer({ incidentsOnly = false }: { incidentsOnly?: boolean }) {
  const { data: projects } = useApi(api.projects);
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">{incidentsOnly ? "Troubleshooting" : "Engineer Mode"}</h1>
        <p className="mt-1 text-ink-400">
          {incidentsOnly
            ? "Real incidents injected into pre-deployed projects. Investigate, fix, verify, then reset."
            : "Pre-deployed projects in resettable namespaces. Explore the architecture, break things, fix them."}
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        {projects?.filter((p) => !incidentsOnly || p.incidents.length).map((p) => (
          <Card key={p.id} title={p.name} action={<Badge>{p.status}</Badge>}>
            {!incidentsOnly && (
              <>
                <p className="text-sm text-ink-200">{p.summary}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {p.components.map((c) => (
                    <span key={c} className="rounded bg-ink-800 px-2 py-0.5 text-xs text-ink-400">{c}</span>
                  ))}
                </div>
              </>
            )}
            {p.incidents.length > 0 && (
              <ul className="mt-4 space-y-1.5">
                {p.incidents.map((i) => (
                  <li key={i.id} className="flex items-center gap-2 text-sm">
                    <AlertTriangle className="h-4 w-4 shrink-0 text-ink-400" />
                    <span className="flex-1">{i.title}</span>
                    <Badge>{i.severity}</Badge>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-4 flex items-center justify-between border-t border-ink-700 pt-3 text-xs text-ink-400">
              <span>Arrives in Stage {p.stage}</span>
              <button disabled className="rounded-md bg-ink-800 px-3 py-1.5 text-ink-400 disabled:opacity-50"
                title="Available once the project is deployed">Reset lab</button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
