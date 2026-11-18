#!/bin/sh
# Start the learner's own rootless Docker daemon, then stay alive until the
# session's deadline. Shells arrive via `docker exec`; nothing listens on a port.
set -eu
dockerd-entrypoint.sh >/tmp/dockerd.log 2>&1 &
sleep "${DEVOPSLAB_MAX_SECONDS:-14400}"
