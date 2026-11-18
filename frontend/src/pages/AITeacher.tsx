import { Bot, CheckCircle2, ShieldCheck } from "lucide-react";
import { api } from "../api";
import { useApi } from "../lib/useApi";
import { Card, Code, ErrorBox, PageHeader, PlannedBadge, StatusDot } from "../components/ui";

const FEATURES = [
  ["Ask Anything", "Answers at your level, with a follow-up question to check understanding."],
  ["Teach Me Step by Step", "One concept at a time: analogy, YAML explained line by line, a hands-on step, a check."],
  ["Explain This Command", "What it does, why you'd use it, every flag, and the output to expect."],
  ["Explain This YAML", "Line by line, what's missing, and what production would need."],
  ["Debug My Error", "What happened, why, how to investigate, the fix, and how to prevent it."],
  ["Review My Configuration", "Issues by severity with suggested changes."],
  ["Generate Practice Exercises", "New exercises for the topic you're on."],
  ["Conduct Mock Interviews", "One question at a time, scored with feedback."],
  ["Test My Knowledge", "Graded quizzes that track your weak areas."],
  ["Give Me a Real-World Scenario", "An incident brief that can launch a matching lab."],
];

const PRIVACY = [
  "Runs on your Mac with Ollama. No external AI API needed.",
  "Terminal output and files are sent only when you choose, and you see exactly what's sent.",
  "Secrets, tokens and kubeconfigs are stripped before anything reaches a model.",
  "It only suggests commands. Nothing runs until you approve it.",
  "Pick your own models, or turn AI off completely.",
];

export default function AITeacher() {
  const { data, error } = useApi(api.infra);
  const ollama = data?.components.find((c) => c.id === "ollama");
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader title="AI Teacher" subtitle="Your personal DevOps instructor, running locally on Ollama.">
        <PlannedBadge phase={9} />
      </PageHeader>
      <Card title="Ollama connection">
        {error && <ErrorBox error={error} />}
        {!ollama && !error && <p className="text-sm text-ink-400">Checking…</p>}
        {ollama && (
          <div className="flex items-start gap-3 text-sm">
            <span className="mt-1.5"><StatusDot status={ollama.status} /></span>
            <div>
              <p className="text-white">{ollama.message}{ollama.version && <span className="ml-2 font-mono text-xs text-ink-400">v{ollama.version}</span>}</p>
              {ollama.remediation && ollama.status !== "ok" && (
                <p className="mt-1 text-ink-400">{ollama.remediation.split("`").map((p, i) => (i % 2 ? <Code key={i}>{p}</Code> : p))}</p>
              )}
              <p className="mt-2 text-xs text-ink-400">
                Suggested models when this arrives: <Code>qwen2.5-coder:7b</Code> for commands and YAML,{" "}
                <Code>llama3.2:3b</Code> for explanations. You choose; nothing downloads automatically.
              </p>
            </div>
          </div>
        )}
      </Card>
      <Card title="What it will do">
        <ul className="grid gap-3 sm:grid-cols-2">
          {FEATURES.map(([name, desc]) => (
            <li key={name} className="flex gap-3 rounded-lg bg-ink-800 p-3">
              <Bot className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
              <div><div className="font-medium text-white">{name}</div><p className="text-sm text-ink-400">{desc}</p></div>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-ink-400">An "Ask AI Teacher" button will also appear in every module, terminal and challenge.</p>
      </Card>
      <Card title="Privacy and safety">
        <ul className="space-y-2 text-sm text-ink-200">
          {PRIVACY.map((t) => (
            <li key={t} className="flex gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" />{t}</li>
          ))}
        </ul>
      </Card>
      <p className="flex items-center gap-2 text-xs text-ink-400">
        <CheckCircle2 className="h-4 w-4" /> Design: docs/ai-teacher.md
      </p>
    </div>
  );
}
