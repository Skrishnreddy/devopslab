# DevOpsLab: run `make help` for the list.
.DEFAULT_GOAL := help
SHELL := /bin/bash
S := infra/scripts
# Pinned backend deps support Python 3.12-3.13 (pydantic-core can't build on 3.14 yet).
PYTHON ?= $(shell command -v python3.12 || command -v python3.13 || echo python3)

help: ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ---- infrastructure ---------------------------------------------------------
prereqs: ## Install colima, docker, kind, kubectl, helm, node, python (Homebrew)
	@$(S)/prereqs.sh

up: ## Start Colima + kind cluster + ingress + metrics-server
	@$(S)/up.sh

images: ## Build the terminal image and load it into the cluster (make up does this too)
	@$(S)/images.sh

down: ## Stop the Colima VM (cluster kept)
	@$(S)/down.sh

destroy: ## Delete the kind cluster and Colima profile
	@$(S)/down.sh --destroy

status: ## Show VM, node and pod health
	@$(S)/status.sh

# ---- app ----------------------------------------------------------------------
install: ## Install backend + frontend dependencies
	@$(PYTHON) -c 'import sys; v=sys.version_info[:2]; sys.exit(0 if (3,12)<=v<(3,14) else "Need Python 3.12 or 3.13, found %d.%d. Run: brew install python@3.12" % v)'
	cd backend && $(PYTHON) -m venv --clear .venv && .venv/bin/pip install -q -r requirements-dev.txt
	cd frontend && npm ci

backend: ## Run the API on 127.0.0.1:8000
	cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app

frontend: ## Run the UI on http://127.0.0.1:5173
	cd frontend && npm run dev

dev: ## Run backend and frontend together (Ctrl+C stops both)
	@$(S)/dev.sh

token: ## Print your login link
	@$(S)/token.sh

schemas: ## Regenerate content JSON Schemas
	cd backend && .venv/bin/python -m app.content.schemas

# ---- quality ------------------------------------------------------------------
test: test-backend test-frontend lint-shell ## Everything CI runs

test-backend: ## Backend tests + lint (also validates content and migrations)
	cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q

test-frontend: ## Frontend type check, lint, tests and build
	cd frontend && npx tsc -b && npm run lint && npm test && npm run build

lint-shell: ## ShellCheck the infra scripts
	backend/.venv/bin/shellcheck -x $(S)/*.sh

secrets-scan: ## Scan the git history for secrets (needs gitleaks)
	@command -v gitleaks >/dev/null || { echo "Install with: brew install gitleaks"; exit 1; }
	gitleaks git --redact --verbose .

# ---- planned ------------------------------------------------------------------
monitoring-on: ## Planned (Phase 7); raise COLIMA_MEMORY to 8 first
	@$(S)/monitoring.sh on

monitoring-off: ## Remove monitoring to free RAM
	@$(S)/monitoring.sh off

.PHONY: help prereqs up images down destroy status install backend frontend dev token schemas test test-backend \
	test-frontend lint-shell secrets-scan monitoring-on monitoring-off
