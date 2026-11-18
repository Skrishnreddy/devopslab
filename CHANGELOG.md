# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [SemVer](https://semver.org/).

## [Unreleased]

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
