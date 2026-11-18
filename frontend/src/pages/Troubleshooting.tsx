import { api, type Level } from "../api";
import { useApi } from "../lib/useApi";
import { Badge, Card, ErrorBox, PageHeader, PlannedBadge } from "../components/ui";

const ORDER: Level[] = ["beginner", "intermediate", "advanced"];

export default function Troubleshooting() {
  const { data, error } = useApi(api.challenges);
  const sorted = [...(data ?? [])].sort((a, b) => ORDER.indexOf(a.difficulty) - ORDER.indexOf(b.difficulty));
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Troubleshooting"
        subtitle="Real failures injected into a lab. Investigate in the terminal, use up to three hints, then validate your fix." />
      {error && <ErrorBox error={error} />}
      <Card title={`Kubernetes scenarios (${sorted.length})`} action={<PlannedBadge phase={6} />}>
        <ul className="divide-y divide-ink-700">
          {sorted.map((c) => (
            <li key={c.id} className="flex items-start gap-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="font-medium text-white">{c.name}</div>
                <p className="mt-0.5 text-sm text-ink-400">{c.description.split("\n")[0]}</p>
              </div>
              <Badge>{c.difficulty}</Badge>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
