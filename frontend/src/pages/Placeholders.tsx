import { useParams } from "react-router-dom";
import { SquareTerminal } from "lucide-react";
import { Card } from "../components/ui";

export function Topic() {
  const { id = "" } = useParams();
  const name = id === "devsecops" ? "DevSecOps" : id.charAt(0).toUpperCase() + id.slice(1);
  return (
    <div className="mx-auto max-w-3xl">
      <Card title={name}>
        <p className="text-ink-200">
          Every topic will get a working pre-deployed example, a terminal, an explanation, hands-on
          tasks, troubleshooting hints and a reset button. {name} arrives after the Kubernetes track.
        </p>
      </Card>
    </div>
  );
}

const TERMINALS = [
  { id: "linux", name: "Linux", sample: "whoami && systemctl status" },
  { id: "kubernetes", name: "Kubernetes", sample: "kubectl get pods -A" },
  { id: "docker", name: "Docker / DevOps", sample: "docker ps" },
];

export function Terminal() {
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex gap-2">
        {TERMINALS.map((t, i) => (
          <span key={t.id} className={`rounded-t-md px-4 py-2 text-sm ${i === 1 ? "bg-ink-900 text-white" : "text-ink-400"}`}>
            <SquareTerminal className="mr-1.5 inline h-4 w-4" />{t.name}
          </span>
        ))}
      </div>
      <div className="h-96 rounded-b-xl rounded-tr-xl border border-ink-700 bg-black p-4 font-mono text-sm">
        <span className="text-ok">lab@devopslab</span>:<span className="text-accent">~</span>$ kubectl get pods -A
        <p className="mt-4 text-ink-400">
          # The integrated terminal arrives in Stage 3. Each tab runs inside a sandbox pod in the
          lab cluster, so it can't touch your Mac.
        </p>
      </div>
    </div>
  );
}
