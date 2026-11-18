#!/usr/bin/env bash
# Quick health report for the lab.
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"
colima list 2>/dev/null | (grep -E "PROFILE|$COLIMA_PROFILE" || true)
if k cluster-info >/dev/null 2>&1; then
  k get nodes
  echo; k get pods -A --no-headers | awk '{print $4}' | sort | uniq -c
  echo; k top nodes 2>/dev/null || warn "metrics not ready yet"
else
  warn "Cluster '$CLUSTER_NAME' is not reachable. Run: make up"
fi
