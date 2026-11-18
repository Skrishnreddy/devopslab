#!/usr/bin/env bash
# Prints the login link. The token lives in ~/.devopslab/login-token (mode 0600).
set -euo pipefail
DATA_DIR="${DEVOPSLAB_DATA_DIR:-$HOME/.devopslab}"
TOKEN_FILE="$DATA_DIR/login-token"
if [[ ! -f "$TOKEN_FILE" ]]; then
  echo "No token yet. Start the backend once with 'make dev' to create it." >&2
  exit 1
fi
echo "http://127.0.0.1:5173/login#token=$(tr -d '[:space:]' < "$TOKEN_FILE")"
