#!/usr/bin/env bash
# Shared helpers for DevOpsLab scripts.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/infra/config.env"
export KUBECONFIG="${KUBECONFIG_DEVOPSLAB:-$HOME/.kube/devopslab}"
export DOCKER_CONTEXT="colima-$COLIMA_PROFILE"
KCTX="kind-$CLUSTER_NAME"

info() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$1 not found. Run: make prereqs"; }
k()    { kubectl --context "$KCTX" "$@"; }

# `colima start` switches the global Docker context; scripts that start a VM
# save the user's context first and put it back on exit.
PREV_DOCKER_CONTEXT=""
save_docker_context() { PREV_DOCKER_CONTEXT="$(env -u DOCKER_CONTEXT docker context show 2>/dev/null || true)"; }
restore_docker_context() {
  local now
  now="$(env -u DOCKER_CONTEXT docker context show 2>/dev/null || true)"
  if [[ -n "$PREV_DOCKER_CONTEXT" && "$now" != "$PREV_DOCKER_CONTEXT" ]]; then
    env -u DOCKER_CONTEXT docker context use "$PREV_DOCKER_CONTEXT" >/dev/null 2>&1 \
      && info "Docker context restored to '$PREV_DOCKER_CONTEXT'"
  fi
  return 0
}
