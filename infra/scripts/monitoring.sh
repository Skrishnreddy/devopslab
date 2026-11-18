#!/usr/bin/env bash
# Stage 8 placeholder. Monitoring is OFF by default to keep RAM free.
source "$(dirname "$0")/lib.sh"
case "${1:-}" in
  on)  die "Monitoring arrives in Stage 8. Before enabling, raise COLIMA_MEMORY to 8 in infra/config.env." ;;
  off) k delete namespace monitoring --ignore-not-found ;;
  *)   die "usage: monitoring.sh on|off" ;;
esac
