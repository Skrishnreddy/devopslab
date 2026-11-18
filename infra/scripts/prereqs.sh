#!/usr/bin/env bash
# Installs the CLI tools DevOpsLab needs via Homebrew. Safe to re-run.
source "$(dirname "$0")/lib.sh"
[[ "$(uname -s)" == "Darwin" ]] || warn "Written for macOS; on Linux install these tools yourself."
need brew
for pkg in colima docker kind kubectl helm node python@3.12; do
  if brew list --formula "$pkg" >/dev/null 2>&1; then info "$pkg already installed"
  else info "Installing $pkg"; brew install "$pkg"; fi
done
info "Done. Next: make up"
