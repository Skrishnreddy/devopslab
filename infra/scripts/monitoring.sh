#!/usr/bin/env bash
# Planned (Phase 7). Monitoring is OFF by default to keep RAM free.
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"
case "${1:-}" in
  on)  die "Monitoring arrives in Phase 7. Before enabling, raise COLIMA_MEMORY to 8 in infra/config.env." ;;
  off) k delete namespace monitoring --ignore-not-found ;;
  *)   die "usage: monitoring.sh on|off" ;;
esac
