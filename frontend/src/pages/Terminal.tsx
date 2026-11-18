import { Lock, SquareTerminal } from "lucide-react";
import { Card, PageHeader, PlannedBadge } from "../components/ui";

const ENVS = [
  { name: "Linux", desc: "Ubuntu sandbox for shell, process, service and log practice." },
  { name: "Kubernetes", desc: "kubectl and helm, scoped to your lab namespaces. Never cluster-admin." },
  { name: "Docker / DevOps", desc: "Docker CLI against an isolated rootless daemon, never your Mac's." },
];

export default function Terminal() {
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Terminal" subtitle="Real shells running in disposable lab containers.">
        <PlannedBadge phase={2} />
      </PageHeader>
      <div className="grid gap-4 md:grid-cols-3">
        {ENVS.map((e) => (
          <Card key={e.name}>
            <SquareTerminal className="h-5 w-5 text-accent" />
            <div className="mt-2 font-semibold text-white">{e.name}</div>
            <p className="mt-1 text-sm text-ink-400">{e.desc}</p>
          </Card>
        ))}
      </div>
      <Card className="mt-6" title="Security boundaries">
        <ul className="space-y-2 text-sm text-ink-200">
          {["Each session runs in its own sandbox pod, never on your Mac.",
            "Non-root, all capabilities dropped, CPU and memory limits, read-only root filesystem.",
            "No host Docker socket. Default-deny network policy.",
            "Requires your login session. Idle sessions close after 30 minutes."].map((t) => (
            <li key={t} className="flex gap-2"><Lock className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" />{t}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
