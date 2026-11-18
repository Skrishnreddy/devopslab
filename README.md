# DevOpsLab

**Learn. Build. Break. Troubleshoot. Master.**

DevOpsLab is an open-source, local-first DevOps engineering playground. It runs a
real Kubernetes cluster on your laptop and gives you two ways to learn:

- **Learn Mode**: structured, topic-by-topic modules from beginner to advanced.
- **Engineer Mode**: production-style projects you deploy, explore, break,
  troubleshoot and reset.
- **AI Teacher** (Phase 9): a personal DevOps instructor running locally on
  [Ollama](https://ollama.com). It explains, demonstrates, quizzes you and helps
  you debug, and never runs a command without your approval.

> **Status: Phase 1 (Foundation) of 11.** The infrastructure, dashboard, auth,
> health checks and learning catalog work today. Terminals, CloudMart, lessons
> and the troubleshooting engine are being built next. Everything not built yet
> is labelled **Planned** in the UI. See the [roadmap](#roadmap).

![Dashboard](docs/screenshots/dashboard.png)

## Features

| Available now (Phase 1) | Planned |
|---|---|
| One-command local cluster: Colima + 3-node kind, ingress, metrics-server | Browser terminals (Linux, Kubernetes, Docker) in isolated pods · Phase 2 |
| Live infrastructure health: Colima, Docker Engine, kind, kubectl, Helm, Kubernetes API | Deployments, services, logs, events · Phase 3 |
| Live cluster summary, nodes and pods | CloudMart microservices app + lab reset · Phase 4 |
| Learn Mode catalog (15 tracks, 20 Kubernetes modules) with progress tracking | Lessons, exercises with automatic checks, quizzes · Phase 5 |
| Projects and troubleshooting catalogs | 15 Kubernetes troubleshooting scenarios with 3 progressive hints · Phase 6 |
| Local login, session cookies, Origin checks | Prometheus, Grafana, Loki · Phase 7 |
| Content as YAML with JSON Schemas | Trivy, Kyverno, RBAC, NetworkPolicies · Phase 8 |
| SQLite with migrations (PostgreSQL-ready) | **Local AI Teacher** on Ollama: lessons, debugging help, quizzes, mock interviews · Phase 9 |
| Ollama connection check | Jenkins, Argo CD, Terraform, Ansible · Phase 10 |

DevOpsLab never shows sample data: if Colima or the cluster is down, the
dashboard says so and tells you the command that fixes it.

## Supported platforms

| Platform | Status |
|---|---|
| macOS on Apple Silicon (M1–M4), 16 GB RAM | Primary target |
| macOS on Intel | Should work, untested |
| Linux | Planned (provider interface ready) |
| Windows (WSL2) | Planned |

Docker Desktop is **not** required.

## Install (macOS, Apple Silicon)

Prerequisites: [Homebrew](https://brew.sh), about 15 GB free disk.

```bash
git clone <your fork or this repo> devopslab && cd devopslab
make prereqs   # colima, docker CLI, kind, kubectl, helm, node, python
make up        # Colima VM + kind cluster + add-ons (first run ~5 min)
make install   # backend venv + frontend packages
make dev       # API on 127.0.0.1:8000, UI on 127.0.0.1:5173
```

`make dev` prints a login link. Open it, or run `make token` in another
terminal to print it again. The token is stored in `~/.devopslab/login-token`
(readable only by you).

Other commands: `make status`, `make down` (stop the VM, keep the cluster),
`make destroy` (remove everything), `make help`.

The cluster uses its own kubeconfig at `~/.kube/devopslab`, so your default
`kubectl` context is untouched:

```bash
export KUBECONFIG=~/.kube/devopslab
kubectl get nodes
```

### Resource budget (16 GB Mac)

| Component | Budget |
|---|---|
| macOS | 4 GB |
| Colima VM (`COLIMA_MEMORY=6` in `infra/config.env`) | 6 GB |
| DevOpsLab UI + API | 0.5 GB |
| Browser + editor | 2 GB |
| Headroom | 3.5 GB |

Heavy components (monitoring, Jenkins, Argo CD) are deployed on demand only.

## Architecture

```mermaid
flowchart LR
  user([Learner]) -->|127.0.0.1 only| ui[React UI]
  ui -->|/api/v1 + WebSocket| api[FastAPI]
  api --> db[(SQLite)]
  api --> content[[content/ YAML]]
  api -->|fixed CLI calls| tools[colima · docker · kind · helm]
  api -->|scoped kubeconfig| k8s
  subgraph vm[Colima VM]
    subgraph k8s[kind cluster]
      labs[lab namespaces]
      term[terminal sandbox pods]
    end
  end
```

More: [architecture](docs/architecture.md) · [implementation plan](docs/implementation-plan.md) ·
[API](docs/api.md) · [database](docs/database-schema.md) ·
[AI Teacher](docs/ai-teacher.md) · [terminal security](docs/security/terminal.md) · [lab isolation](docs/security/lab-isolation.md)

## Repository layout

```
backend/   FastAPI app, SQLAlchemy models, Alembic migrations, providers, tests
frontend/  React + TypeScript + Vite + Tailwind UI and tests
content/   tracks, projects, challenges (YAML) + JSON Schemas
infra/     Colima/kind config and setup scripts
docs/      architecture, API, security, screenshots
```

## Screenshots

| Learn Mode | Troubleshooting catalog |
|---|---|
| ![Learn](docs/screenshots/learn.png) | ![Troubleshooting](docs/screenshots/troubleshooting.png) |

## Development

```bash
make install
make dev            # hot reload for both
make test           # backend lint + tests, frontend type check + lint + tests + build, ShellCheck
make schemas        # regenerate content JSON Schemas
make secrets-scan   # gitleaks (brew install gitleaks)
```

Configuration: copy `.env.example` to `backend/.env`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Dashboard shows tools as **missing** | `make prereqs`, then restart `make dev` so PATH is picked up |
| Colima **not running** / Docker Engine unreachable | `make up` |
| `colima start` fails on first run | `colima delete -p devopslab` then `make up`; check free disk |
| Cluster unreachable after reboot | `make up` (resumes the VM; the cluster is kept) |
| Login says the token is invalid | `make token` and use the new link; tokens rotate if the file was deleted |
| Port 5173 or 8000 already in use | Stop the other process or set `DEVOPSLAB_PORT` / Vite `--port` |
| Mac feels slow | `make down` when you're not using the lab; lower `COLIMA_MEMORY`; use a smaller Ollama model |
| Dashboard shows Ollama not reachable | Optional until Phase 9. Install with `brew install ollama`, then `ollama serve` |

## Roadmap

| Phase | Deliverable | Status |
|---|---|---|
| 1 | Foundation: repo, backend, frontend, DB, auth, dashboard, health checks | ✅ |
| 2 | Terminal (xterm.js, isolated pods) | |
| 3 | Kubernetes explorer | |
| 4 | CloudMart + lab management | |
| 5 | Learning engine | |
| 6 | Troubleshooting engine | |
| 7 | Observability | |
| 8 | DevSecOps | |
| 9 | Local AI Teacher (Ollama) | |
| 10 | CI/CD and GitOps | |
| 11 | Public release | |

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) (content can be added with YAML only),
[SECURITY.md](SECURITY.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

[Apache License 2.0](LICENSE).
