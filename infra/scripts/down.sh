#!/usr/bin/env bash
# Stop the lab. Default: stop the VM but keep the cluster (fast restart).
# --destroy: delete the kind cluster and the Colima profile entirely.
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"
if [[ "${1:-}" == "--destroy" ]]; then
  info "Deleting kind cluster '$CLUSTER_NAME'"
  kind delete cluster --name "$CLUSTER_NAME" || true
  info "Deleting Colima profile '$COLIMA_PROFILE'"
  colima delete -p "$COLIMA_PROFILE" -f || true
  info "Deleting the Docker terminal VM '$DOCKER_VM_PROFILE'"
  colima delete -p "$DOCKER_VM_PROFILE" -f >/dev/null 2>&1 || true
else
  if colima status -p "$DOCKER_VM_PROFILE" >/dev/null 2>&1; then
    info "Stopping the Docker terminal VM"
    colima stop -p "$DOCKER_VM_PROFILE"
  fi
  info "Stopping Colima (cluster is kept; 'make up' resumes it)"
  colima stop -p "$COLIMA_PROFILE"
fi
