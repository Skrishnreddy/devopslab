# Implementation plan

Each phase ends with: tests green, the app started and checked by hand, logs
reviewed, docs updated, and a short report (done / not done / next). A failing
phase is fixed before the next starts. Anything not built is shown in the UI
as **Planned** with its phase, never as a fake or disabled control.

## Phase 1: Foundation  ← current

**Build**
- Repo layout, Apache-2.0 and community files, CI (tests, lint, secret scan,
  shellcheck).
- Backend: app factory, config, unified errors, SQLAlchemy models + Alembic,
  provider interfaces (runtime, cluster, terminal, labs, AI).
- Content split into `content/` with Pydantic models and generated JSON
  Schemas; validated at startup.
- Auth: single local admin, token login (printed by `make token`), hashed
  session cookie, Origin check on writes.
- Infra health: real checks of colima, Docker Engine, kind, kubectl, helm,
  and the cluster API, each with version and a fix-it hint.
- UI: login, sidebar (14 sections from the spec + AI Teacher), Learn/Engineer switch, dashboard,
  Kubernetes nodes/pods, Learn track with progress, Projects catalog, Settings,
  Planned pages.

**Acceptance criteria**
1. `make install && make dev` starts both servers on 127.0.0.1; `make token`
   prints a login URL.
2. Every `/api/v1` route except health/login returns 401 without a session.
3. Infra health reports each tool as ok/missing/error from real commands; with
   Colima stopped the dashboard says so and shows the command to fix it.
4. With the cluster up, node/pod/deployment counts match `kubectl`.
5. Module progress persists across restarts; dashboard percentages are
   computed from the database.
6. No page shows sample data; empty states say what's missing.
7. Invalid content YAML stops startup with the file and field named.
8. Backend unit + API tests, frontend tests, lint and build pass in CI.

## Phase 2: Terminal

xterm.js tabs (Linux / Kubernetes / Docker), session API, WebSocket bridged to
the Kubernetes exec API, sandbox pod profiles, resize, copy/paste, history
(shell-side), clear, connection status, idle/absolute timeouts, reaper.
**Accept:** the tests listed in `docs/security/terminal.md` pass; terminals
work in Chrome and Safari; closing a tab deletes its pod within 10 s.

## Phase 3: Kubernetes

Cluster discovery (contexts), namespaces, deployments, services, events, pod
detail, logs (follow), YAML view. Colima/kind lifecycle buttons
(start/stop) that call the same scripts as the Makefile.
**Accept:** every list matches `kubectl` output; logs stream; errors from
the API are shown verbatim.

## Phase 4: CloudMart

Real app: React storefront, FastAPI API, PostgreSQL (StatefulSet + PVC),
Redis, NGINX Ingress. ARM64 + AMD64 images, Dockerfiles, plain manifests and a
Helm chart. Lab engine: create/start/stop/delete/reset/status/usage, quotas,
timeouts, cleanup.
**Accept:** "Deploy CloudMart" brings it up at http://localhost:8080 within
3 min on an M4; reset twice in a row is idempotent; a failed reset shows the
failing step.

## Phase 5: Learning engine

Module schema extended with lessons (concept, use case, architecture, commands,
YAML, exercises with automated checks, expected output, quiz, troubleshooting
exercise). First 5 Kubernetes modules complete end to end.
**Accept:** a learner completes 5 exercises whose checks run against the lab.

## Phase 6: Troubleshooting

Scenario engine (schema in `content/schemas/challenge.schema.json`), fault
injection, symptom checks, 3 progressive hints, validation, root cause and
solution on request, reset. All 15 Kubernetes scenarios authored; Node
NotReady uses a disposable kind cluster.
**Accept:** at least 5 scenarios pass an automated inject → fix → validate test
on a real kind cluster in CI.

## Phase 7: Observability

On-demand Prometheus, Grafana, Loki (kube-prometheus-stack trimmed + Loki
single binary), CloudMart metrics, dashboards, an alert. Memory check before
deploy.

## Phase 8: DevSecOps

Trivy scans (images, manifests), Kyverno policies, RBAC and NetworkPolicy
labs, security challenges.

## Phase 9: Local AI Teacher and intelligent learning engine

Design: [ai-teacher.md](ai-teacher.md). Ollama is the default runtime behind a
model-independent `AIProvider` interface; everything runs locally.

1. Integrate Ollama with FastAPI (status, models, streaming chat).
2. Configurable local LLM providers and per-role model selection.
3. Teaching modes and learning context.
4. Topic-based teaching workflows (step-by-step lessons).
5. Terminal context and error analysis.
6. Kubernetes, Docker, Terraform and Linux troubleshooting help.
7. Quizzes, assignments, mock interviews and assessments.
8. Learner progress and weak areas.
9. Model selection and connection status.
10. Privacy controls (redaction, consent) and command execution approval.

**Accept:** the criteria in `docs/ai-teacher.md`.

## Phase 10: CI/CD and GitOps

Jenkins (on demand), local registry, pipeline building CloudMart images, Trivy
gate, deploy to cluster, rollback; Helm; Argo CD app-of-apps; Terraform and
Ansible tracks.

## Phase 11: Public release

Docs site, screenshots, security review, dependency licence review, release
packaging, GitHub Actions for e2e on a kind cluster, contribution guide.

## MVP definition of done → phase

| # | Requirement | Phase |
|---|---|---|
| 1 | App starts locally | 1 |
| 2 | Dashboard shows real infrastructure | 1 |
| 3 | Functional Linux terminal | 2 |
| 4 | Functional Kubernetes terminal | 2 |
| 5 | Inspect real Pods | 1 (list), 3 (detail, logs) |
| 6 | Deploy CloudMart | 4 |
| 7 | Access learning modules | 1 (catalog), 5 (lessons) |
| 8 | Complete 5 Kubernetes exercises | 5 |
| 9 | Troubleshoot 5 working scenarios | 6 |
| 10 | Reset a lab | 4 |
| 11 | Tests for major features | every phase |
| 12 | Install docs work on Apple Silicon | 1, re-verified each phase |
