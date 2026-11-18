import { useParams } from "react-router-dom";
import { api } from "../api";
import { useApi } from "../lib/useApi";
import { Card, ErrorBox, PageHeader, PlannedBadge } from "../components/ui";

export default function Topic() {
  const { id = "" } = useParams();
  const { data, error } = useApi(api.tracks);
  const track = data?.find((t) => t.id === id);
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  if (!track) return <ErrorBox error={new Error(`No track called "${id}"`)} title="Not found" />;
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={track.name} subtitle={track.description}>
        {track.status === "planned" && <PlannedBadge phase={track.phase} />}
      </PageHeader>
      <Card title="What this section will include">
        <ul className="list-inside list-disc space-y-1 text-sm text-ink-200">
          <li>A working pre-deployed example to explore</li>
          <li>A terminal inside an isolated lab</li>
          <li>Concepts, real-world use cases and architecture</li>
          <li>Hands-on exercises with automatic checks and expected output</li>
          <li>Troubleshooting exercises with progressive hints</li>
          <li>A reset button to restore the lab</li>
        </ul>
      </Card>
    </div>
  );
}
