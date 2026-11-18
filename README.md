# DevOpsLab

Your personal DevOps and Kubernetes engineering playground, running entirely on
your Mac. Two ways to use it:

- **Learn Mode**: structured, topic-by-topic modules from beginner to advanced.
- **Engineer Mode**: pre-deployed projects with real incidents, a terminal,
  hints, and a reset button.

## Quick start (macOS, Apple silicon)

```bash
make prereqs     # colima, docker, kind, kubectl, helm, node, python via Homebrew
make up          # Colima VM + 3-node kind cluster + ingress + metrics-server (~3-5 min first time)
make install     # backend venv + frontend packages
make dev         # API on 127.0.0.1:8000, dashboard on http://127.0.0.1:5173
```

`make status` shows cluster health, `make down` stops the VM (keeps the
cluster), `make destroy` removes everything. `make help` lists all targets.

The cluster uses its own kubeconfig at `~/.kube/devopslab`, so it never
changes your default `kubectl` context. To use it from your own shell:

```bash
export KUBECONFIG=~/.kube/devopslab
kubectl get nodes
```

## Resource budget (16 GB MacBook Air)

The Colima VM is the lab's whole budget; edit `infra/config.env` to change it.

| Component                  | Budget  | Where              |
|----------------------------|---------|--------------------|
| macOS                      | 4 GB    | host               |
| Colima VM (kind + add-ons) | 6 GB    | `COLIMA_MEMORY=6`  |
|  ↳ cluster + system pods   | ~4 GB   | inside VM          |
|  ↳ CloudMart (Stage 4)     | ~1.5 GB | inside VM          |
| DevOpsLab UI + API         | ~0.5 GB | host               |
| Browser + VS Code          | ~2 GB   | host               |
| Headroom                   | ~3.5 GB |                    |

Monitoring (Prometheus, Grafana, Loki) is **off by default**. When Stage 8
lands, raise `COLIMA_MEMORY` to 8 before turning it on.

## Layout

```
infra/          Stage 1: Colima + kind config, setup scripts
backend/        FastAPI: cluster status, progress (SQLite), lab engine, terminal
frontend/       React + TypeScript + Tailwind dashboard
labs/           Engineer Mode projects (kustomize) and challenge definitions
docs/           Architecture and build stages
```

## Build stages

| Stage | Deliverable                          | Status |
|-------|--------------------------------------|--------|
| 1     | Local Kubernetes infrastructure      | ✅     |
| 2     | DevOpsLab dashboard                  | ✅     |
| 3     | Integrated terminal (xterm.js)       |        |
| 4     | Pre-deployed CloudMart               |        |
| 5     | Kubernetes learning modules          |        |
| 6     | Troubleshooting challenge engine     |        |
| 7     | AI hints (Ollama, optional)          |        |
| 8     | Prometheus and Grafana               |        |
| 9     | Jenkins and Argo CD                  |        |
| 10    | kubeadm multi-node environment       |        |

See [docs/architecture.md](docs/architecture.md) for how the pieces fit.
