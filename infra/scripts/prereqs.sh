#!/usr/bin/env bash
# Installs the CLI tools DevOpsLab needs via Homebrew. Safe to re-run.
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"
[[ "$(uname -s)" == "Darwin" ]] || warn "Written for macOS; on Linux install these tools yourself."
need brew
# formula:command pairs. A tool already on PATH (e.g. Docker Desktop's docker CLI)
# is left alone so we don't shadow the user's existing setup.
for pair in colima:colima docker:docker kind:kind kubernetes-cli:kubectl helm:helm node:node python@3.12:python3.12; do
  formula="${pair%%:*}" cmd="${pair##*:}"
  if command -v "$cmd" >/dev/null 2>&1; then info "$cmd already installed ($(command -v "$cmd"))"
  else info "Installing $formula"; brew install "$formula"; fi
done
info "Done. Next: make up"
