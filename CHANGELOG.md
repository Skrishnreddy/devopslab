# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added (Phase 3: Kubernetes views)
- Kubernetes explorer: pods, deployments, services, events and namespaces with a namespace filter;
  columns match `kubectl get`.
- Pod details: container state and last state (exit codes), restarts, conditions and events; logs with
  container picker, previous-container logs and live follow (server-sent events); YAML view for pods,
  deployments, services, config maps, namespaces and nodes (never Secrets).
- Kubernetes API errors are shown verbatim (e.g. `pods "x" not found`).
- Start and stop the lab from the UI with the same scripts as `make up` / `make down`, with their
  real output.

### Added (Phase 2: Terminal)
- Browser terminals (xterm.js) with tabs, resize, clear, copy/paste, connection status and reconnect.
- Each terminal is a disposable sandbox pod in `devopslab-terminal`: non-root, all capabilities
  dropped, read-only root filesystem, seccomp, CPU/memory/storage limits, Pod Security `restricted`,
  default-deny network policy, no host mounts or Docker socket.
- Linux profile (no cluster credentials) and Kubernetes profile (`lab-learner` service account:
  edit in `lab-playground`, read-only elsewhere, never cluster-admin).
- Terminal API and WebSocket bridge to the Kubernetes exec API with cookie and Origin checks,
  per-user ownership, 4 sessions per user, 30 min idle and 4 h hard limits, orphan cleanup,
  and an audit table (no keystrokes stored).
- `make images` builds the terminal image in Colima and loads it into kind (`make up` runs it).

### Added (Phase 2b: Docker terminal)
- Docker terminal with its own rootless Docker engine per session, running in a separate small
  Colima VM (`devopslab-docker`) that starts on demand and stops after 10 idle minutes
  (`make docker-vm-up` / `make docker-vm-down`). No Mac folders mounted; a firewall keeps
  sandboxes away from the Mac's localhost services and the VM itself.

### Added (Phase 1: Foundation)
- Local Kubernetes infrastructure: Colima + 3-node kind cluster, ingress-nginx, metrics-server
  (`make up`), with a 6 GB VM budget and monitoring off by default.
- FastAPI backend with SQLAlchemy models and Alembic migrations (SQLite, PostgreSQL-compatible).
- Local token authentication with HttpOnly session cookies and Origin checks on writes.
- Real infrastructure health checks for Colima, Docker Engine, kind, kubectl, Helm and the Kubernetes API.
- Cluster summary and pod list from the live API server.
- Content in `content/` (15 tracks, 5 projects, 15 troubleshooting scenarios) validated against
  generated JSON Schemas.
- React + TypeScript + Tailwind UI: login, dashboard, Learn Mode progress tracking, Kubernetes view,
  projects and troubleshooting catalogs, settings; unbuilt features clearly marked Planned.
- Architecture, API, database, terminal security and lab isolation documentation.
- CI: backend and frontend tests, lint, type checks, ShellCheck and secret scanning.
- AI Teacher design (Phase 9): Ollama-first, model-independent provider interface; dashboard
  shows whether Ollama is reachable; AI Teacher section marked Planned.

### Fixed
- `make install` now uses Python 3.12/3.13 even when the default `python3` is 3.14.
- `make prereqs` no longer installs tools already on PATH (e.g. Docker Desktop's CLI).
- `make up` restores your previous Docker context after starting Colima.
- Infrastructure health's kind check no longer depends on the global Docker context.
- Frontend dev dependencies updated (vitest 4.1.12); `npm audit` is clean.

### Changed
- Roadmap: Local AI Teacher is Phase 9; CI/CD and GitOps move to Phase 10; public release to Phase 11.
