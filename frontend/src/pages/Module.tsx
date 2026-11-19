import { Fragment, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Copy, Lightbulb, Loader2, PlayCircle, RotateCcw, SquareTerminal, Wrench, XCircle } from "lucide-react";
import { api, type CheckRun, type ExerciseView, type LessonView, type QuizResult } from "../api";
import { useApi } from "../lib/useApi";
import { Badge, Card, ErrorBox, PageHeader } from "../components/ui";

const btn = "inline-flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-900 px-3 py-1.5 text-sm text-ink-200 hover:border-accent hover:text-white disabled:opacity-50";
const pre = "overflow-auto rounded-lg bg-ink-950 p-3 font-mono text-xs leading-relaxed text-ink-200";

/** `code` and **bold** inside a line of lesson text. */
function inline(text: string): ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("`") ? <code key={i} className="rounded bg-ink-800 px-1 py-0.5 font-mono text-[0.85em] text-accent">{part.slice(1, -1)}</code>
      : part.startsWith("**") ? <strong key={i} className="text-white">{part.slice(2, -2)}</strong>
        : <Fragment key={i}>{part}</Fragment>);
}

/** Lesson text: blank lines split paragraphs; lines indented 4+ spaces are code; "1." lines are steps. */
export function Prose({ text }: { text: string }) {
  const blocks = text.trim().split(/\n\s*\n/);
  return (
    <div className="space-y-3 text-sm leading-relaxed text-ink-200">
      {blocks.map((b, i) => {
        const lines = b.split("\n");
        if (lines.every((l) => /^ {4}/.test(l) || !l.trim())) {
          return <pre key={i} className={pre}>{lines.map((l) => l.slice(4)).join("\n")}</pre>;
        }
        if (lines.every((l) => /^\d+\.\s/.test(l) || /^ {3}/.test(l))) {
          const items = b.split(/\n(?=\d+\.\s)/).map((l) => l.replace(/^\d+\.\s/, "").replace(/\n\s+/g, " "));
          return <ol key={i} className="list-decimal space-y-1 pl-5">{items.map((it, j) => <li key={j}>{inline(it)}</li>)}</ol>;
        }
        return <p key={i}>{inline(b.replace(/\n/g, " "))}</p>;
      })}
    </div>
  );
}

function CopyBlock({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked: text stays selectable */ }
  };
  return (
    <div className="relative">
      <pre className={pre}>{text}</pre>
      <button aria-label={`Copy ${label}`} onClick={copy} className="absolute right-2 top-2 rounded bg-ink-800 p-1 text-ink-400 hover:text-white">
        {copied ? <CheckCircle2 className="h-3.5 w-3.5 text-ok" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

function Results({ run }: { run: { passed: boolean; results: CheckRun["results"] } }) {
  return (
    <ul aria-label="Check results" className="space-y-1.5">
      {run.results.map((r) => (
        <li key={r.description} className="flex gap-2 text-sm">
          {r.passed ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-label="passed" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-bad" aria-label="failed" />}
          <div><div className="text-white">{r.description}</div><div className="font-mono text-xs text-ink-400">{r.observed}</div></div>
        </li>
      ))}
    </ul>
  );
}

function Exercise({ moduleId, e, onChecked }: { moduleId: string; e: ExerciseView; onChecked: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [run, setRun] = useState<{ passed: boolean; results: CheckRun["results"] } | null>(e.last);
  const [output, setOutput] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [solution, setSolution] = useState<string | null>(null);

  const act = async (name: string, fn: () => Promise<void>) => {
    setBusy(name); setError(null);
    try { await fn(); } catch (err) { setError((err as Error).message); } finally { setBusy(null); }
  };
  const check = () => act("check", async () => { const r = await api.checkExercise(moduleId, e.id); setRun(r); onChecked(); });
  const setup = () => act("setup", async () => { setOutput((await api.setupExercise(moduleId, e.id)).output); setRun(null); });
  const reset = () => act("reset", async () => { setOutput((await api.resetExercise(moduleId, e.id)).output); setRun(null); });
  const spin = (n: string) => busy === n && <Loader2 className="h-4 w-4 animate-spin" />;

  return (
    <Card title={e.title} action={
      <span className="flex items-center gap-2">
        <Badge tone={e.kind === "troubleshooting" ? "failed" : "started"}>{e.kind}</Badge>
        {e.passed && <Badge tone="passed">passed</Badge>}
      </span>}>
      <section aria-label={`Exercise ${e.title}`} className="space-y-4">
        <Prose text={e.instructions} />
        {e.expected_output && (
          <div><div className="mb-1 text-xs uppercase tracking-wider text-ink-400">Expected output</div><pre className={pre}>{e.expected_output.trimEnd()}</pre></div>
        )}
        <div className="text-xs text-ink-400">Checks: {e.checks.join(" · ")}</div>
        <div className="flex flex-wrap gap-2">
          {e.has_setup && <button className={btn} disabled={!!busy} onClick={setup}>{spin("setup") || <Wrench className="h-4 w-4" />}Set up</button>}
          <button className={btn} disabled={!!busy} onClick={check}>{spin("check") || <PlayCircle className="h-4 w-4" />}Check</button>
          <button className={btn} disabled={!!busy} onClick={reset} title="Delete what this exercise creates and start over">{spin("reset") || <RotateCcw className="h-4 w-4" />}Reset</button>
          {e.hint && !showHint && <button className={btn} onClick={() => setShowHint(true)}><Lightbulb className="h-4 w-4" />Hint</button>}
          {!solution && <button className="text-sm text-ink-400 hover:text-white" onClick={() => act("solution", async () => setSolution((await api.solution(moduleId, e.id)).solution))}>Show solution</button>}
        </div>
        {error && <p role="alert" className="text-sm text-bad">{error}</p>}
        {output && <pre aria-label="kubectl output" className={pre}>{output.join("\n") || "done"}</pre>}
        {showHint && e.hint && <p className="rounded-lg bg-warn/10 p-3 text-sm text-ink-200"><Lightbulb className="mr-1 inline h-4 w-4 text-warn" />{inline(e.hint)}</p>}
        {run && (
          <div className={`rounded-lg border p-3 ${run.passed ? "border-ok/40 bg-ok/5" : "border-bad/40 bg-bad/5"}`}>
            <div className={`mb-2 text-sm font-medium ${run.passed ? "text-ok" : "text-bad"}`}>{run.passed ? "All checks passed" : "Not yet"}</div>
            <Results run={run} />
          </div>
        )}
        {solution && <div><div className="mb-1 text-xs uppercase tracking-wider text-ink-400">Solution</div><pre className={pre}>{solution.trimEnd()}</pre></div>}
      </section>
    </Card>
  );
}

function Quiz({ moduleId, quiz, onDone }: { moduleId: string; quiz: LessonView["quiz"]; onDone: () => void }) {
  const [answers, setAnswers] = useState<(number | null)[]>(() => quiz.questions.map(() => null));
  const [result, setResult] = useState<QuizResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setError(null);
    try { setResult(await api.submitQuiz(moduleId, answers as number[])); onDone(); } catch (e) { setError((e as Error).message); }
  };
  return (
    <Card title="Quiz" action={quiz.best_percent != null && <span className="text-sm text-ink-400">Best: {quiz.best_percent}%</span>}>
      <form aria-label="Quiz" className="space-y-5" onSubmit={(ev) => { ev.preventDefault(); void submit(); }}>
        {quiz.questions.map((q, i) => {
          const r = result?.results[i];
          return (
            <fieldset key={i} className="space-y-1.5">
              <legend className="mb-1 text-sm font-medium text-white">{i + 1}. {inline(q.question)}</legend>
              {q.options.map((o, j) => (
                <label key={j} className={`flex items-center gap-2 rounded px-2 py-1 text-sm ${r && j === r.answer ? "bg-ok/10 text-ok" : r && answers[i] === j ? "bg-bad/10 text-bad" : "text-ink-200"}`}>
                  <input type="radio" name={`q${i}`} checked={answers[i] === j} onChange={() => { setResult(null); setAnswers((a) => a.map((x, k) => (k === i ? j : x))); }} />
                  {inline(o)}
                </label>
              ))}
              {r && <p className="pl-2 text-xs text-ink-400">{r.correct ? "Correct. " : "Not quite. "}{r.explanation}</p>}
            </fieldset>
          );
        })}
        <div className="flex items-center gap-3">
          <button type="submit" className={btn} disabled={answers.some((a) => a === null)}>Submit answers</button>
          {result && <span role="status" className={result.passed ? "text-sm text-ok" : "text-sm text-bad"}>
            {result.score}/{result.total} ({result.percent}%). {result.passed ? "Passed." : `You need ${quiz.pass_percent}% to pass.`}
          </span>}
        </div>
        {error && <p role="alert" className="text-sm text-bad">{error}</p>}
      </form>
    </Card>
  );
}

export default function Module() {
  const { moduleId = "" } = useParams();
  const { data: m, error, reload } = useApi(() => api.lesson(moduleId));
  if (error) return <div className="mx-auto max-w-4xl space-y-4"><Link to="/learn" className="text-sm text-accent">← Learn</Link><ErrorBox error={error} /></div>;
  if (!m) return <p className="p-6 text-ink-400">Loading lesson…</p>;
  const done = m.exercises.filter((e) => e.passed).length;
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link to="/learn" className="inline-flex items-center gap-1 text-sm text-ink-400 hover:text-white"><ArrowLeft className="h-4 w-4" />{m.track_name}</Link>
      <PageHeader title={`${String(m.order).padStart(2, "0")} · ${m.title}`} subtitle={m.task}>
        <div className="flex items-center gap-2">
          <Badge>{m.level}</Badge>
          <Badge tone={m.status}>{m.status === "not_started" ? "not started" : m.status}</Badge>
        </div>
      </PageHeader>
      <p aria-label="Module progress" className="text-sm text-ink-400">
        {done}/{m.exercises.length} exercises passed · quiz {m.quiz.passed ? "passed" : "not passed yet"}.
        {m.status !== "completed" && " Pass every exercise and the quiz to complete the module."}
      </p>

      <Card title="Concept"><Prose text={m.lesson.concept} /></Card>
      <Card title="When you'll use it"><Prose text={m.lesson.use_case} /></Card>
      <Card title="How it fits together"><pre className={pre}>{m.lesson.architecture.trimEnd()}</pre></Card>
      <Card title="Commands">
        <ul className="space-y-3">
          {m.lesson.commands.map((c) => (
            <li key={c.command}><CopyBlock text={c.command} label={c.command} /><p className="mt-1 text-sm text-ink-400">{inline(c.explanation)}</p></li>
          ))}
        </ul>
      </Card>
      {m.lesson.yaml.map((y) => (
        <Card key={y.title} title={`YAML: ${y.title}`}>
          <div className="mb-2"><Prose text={y.explanation} /></div>
          <CopyBlock text={y.content.trimEnd()} label={y.title} />
        </Card>
      ))}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold text-white">Exercises</h2>
        <Link to="/terminal" className={btn}><SquareTerminal className="h-4 w-4" />Open the terminal</Link>
      </div>
      <p className="-mt-4 text-sm text-ink-400">
        Use a <strong className="text-white">Kubernetes</strong> terminal: it works in <code className="font-mono text-accent">{m.namespace}</code>,
        where checks look. Check reads the real cluster; Reset deletes what the exercise creates there.
      </p>
      {m.exercises.map((e) => <Exercise key={e.id} moduleId={m.id} e={e} onChecked={() => void reload()} />)}
      <Quiz moduleId={m.id} quiz={m.quiz} onDone={() => void reload()} />
    </div>
  );
}
