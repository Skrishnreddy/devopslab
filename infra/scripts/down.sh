#!/usr/bin/env bash
# Stop the lab. Default: stop the VM but keep the cluster (fast restart).
# --destroy: delete the kind cluster and the Colima profile entirely.
source "$(dirname "$0")/lib.sh"
if [[ "${1:-}" == "--destroy" ]]; then
  info "Deleting kind cluster '$CLUSTER_NAME'"
  kind delete cluster --name "$CLUSTER_NAME" || true
  info "Deleting Colima profile '$COLIMA_PROFILE'"
  colima delete -p "$COLIMA_PROFILE" -f || true
else
  info "Stopping Colima (cluster is kept; 'make up' resumes it)"
  colima stop -p "$COLIMA_PROFILE"
fi
