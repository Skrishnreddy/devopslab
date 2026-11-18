#!/usr/bin/env bash
# The Docker terminal's VM (Phase 2b): up | down | status.
# Called by `make docker-vm-up/down` and by the backend when a Docker terminal
# opens or has been idle. Idempotent.
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"
P="$DOCKER_VM_PROFILE"
export DOCKER_CONTEXT="colima-$P"
IMAGE="devopslab/docker-terminal:0.1.0"  # must match DOCKER_IMAGE in backend/app/providers/docker_terminal.py
SHARE="$HOME/.devopslab/docker-vm-share"  # the only folder the VM may see; kept empty

running() { colima status -p "$P" >/dev/null 2>&1; }

case "${1:-status}" in
  up)
    for t in colima docker; do need "$t"; done
    save_docker_context
    trap restore_docker_context EXIT
    if running; then
      info "Docker VM '$P' already running"
    else
      info "Starting Docker VM '$P' ($DOCKER_VM_CPUS CPU, ${DOCKER_VM_MEMORY} GB RAM). Nothing from your Mac is mounted."
      mkdir -p "$SHARE" && chmod 700 "$SHARE"
      colima start -p "$P" --cpu "$DOCKER_VM_CPUS" --memory "$DOCKER_VM_MEMORY" --disk "$DOCKER_VM_DISK" \
        --vm-type vz --mount-type virtiofs --mount "$SHARE"
    fi
    # Refuse to continue if any other Mac folder is visible inside the VM.
    if colima ssh -p "$P" -- test -e "$HOME/Library" 2>/dev/null; then
      colima stop -p "$P" >/dev/null 2>&1 || true
      die "Your home folder is mounted in the Docker VM. Stopped it. Run: colima delete -p $P, then try again."
    fi
    colima ssh -p "$P" -- sudo sh -s < "$ROOT/infra/docker-vm/setup.sh"
    info "Building $IMAGE in the Docker VM (first build takes a few minutes)"
    docker build -q -t "$IMAGE" -f "$ROOT/images/docker-terminal/Dockerfile" "$ROOT/images" >/dev/null
    info "Docker VM ready"
    ;;
  down)
    save_docker_context
    trap restore_docker_context EXIT  # `colima stop` resets the global context too
    if running; then info "Stopping Docker VM '$P'"; colima stop -p "$P"; else info "Docker VM '$P' is not running"; fi
    ;;
  status)
    running && echo running || echo stopped
    ;;
  *) die "usage: $0 up|down|status" ;;
esac
