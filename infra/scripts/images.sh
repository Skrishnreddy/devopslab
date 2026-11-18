#!/usr/bin/env bash
# Build the lab images inside the Colima VM and load them into the kind nodes.
# Nothing is pulled from or pushed to a registry; `kind load` copies the image.
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"
for t in docker kind; do need "$t"; done

TERMINAL_IMAGE="devopslab/terminal:0.1.0"  # must match IMAGE in backend/app/providers/terminal.py

info "Building $TERMINAL_IMAGE (first build takes a few minutes)"
docker build -t "$TERMINAL_IMAGE" "$ROOT/images/terminal"

info "Loading $TERMINAL_IMAGE into kind cluster '$CLUSTER_NAME'"
kind load docker-image "$TERMINAL_IMAGE" --name "$CLUSTER_NAME"
