#!/bin/sh
# Prepares the writable home (an emptyDir) and keeps the pod alive until its
# deadline. The backend opens shells with `exec`; nothing listens on a port.
set -eu
if [ ! -f "$HOME/.bashrc" ]; then
  cp /etc/skel/.profile "$HOME/.profile" 2>/dev/null || true
  cp /etc/devopslab/bashrc "$HOME/.bashrc"
fi
exec sleep "${DEVOPSLAB_MAX_SECONDS:-14400}"
