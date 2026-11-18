#!/usr/bin/env bash
# Runs the API and the UI together; Ctrl+C stops both.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ -x "$ROOT/backend/.venv/bin/uvicorn" ]] || { echo "Run 'make install' first." >&2; exit 1; }
[[ -d "$ROOT/frontend/node_modules" ]] || { echo "Run 'make install' first." >&2; exit 1; }

cleanup() { trap - INT TERM EXIT; kill 0 2>/dev/null || true; }
trap cleanup INT TERM EXIT

(cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app) &
(cd "$ROOT/frontend" && npm run dev) &
wait
