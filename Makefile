# DevOpsLab: run `make help` for the list.
.DEFAULT_GOAL := help
SHELL := /bin/bash
S := infra/scripts
PY := backend/.venv/bin

help: ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

prereqs: ## Install colima, docker, kind, kubectl, helm, node, python (Homebrew)
	@$(S)/prereqs.sh

up: ## Stage 1: start Colima + kind cluster + ingress + metrics-server
	@$(S)/up.sh

down: ## Stop the Colima VM (cluster kept)
	@$(S)/down.sh

destroy: ## Delete the kind cluster and Colima profile
	@$(S)/down.sh --destroy

status: ## Show VM, node and pod health
	@$(S)/status.sh

install: ## Install backend + frontend dependencies
	cd backend && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
	cd frontend && npm install

backend: ## Run the API on 127.0.0.1:8000
	cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

frontend: ## Run the dashboard on http://127.0.0.1:5173
	cd frontend && npm run dev

dev: ## Run backend and frontend together (Ctrl+C stops both)
	@trap 'kill 0' INT TERM; $(MAKE) -s backend & $(MAKE) -s frontend & wait

test: ## Backend tests + frontend type check, lint and build
	cd backend && .venv/bin/pytest -q
	cd frontend && npm run lint && npm run build

monitoring-on: ## Stage 8 (not built yet; raise COLIMA_MEMORY to 8 first)
	@$(S)/monitoring.sh on

monitoring-off: ## Remove monitoring to free RAM
	@$(S)/monitoring.sh off

.PHONY: help prereqs up down destroy status install backend frontend dev test monitoring-on monitoring-off
