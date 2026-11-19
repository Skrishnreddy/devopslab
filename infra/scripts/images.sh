#!/usr/bin/env bash
# Build the lab images inside the Colima VM and load them into the kind nodes.
# Nothing is pulled from or pushed to a registry; `kind load` copies the image.
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"
for t in docker kind; do need "$t"; done

# name:tag=build context. Tags must match the code and manifests that use them:
#   terminal       backend/app/providers/terminal.py (IMAGE)
#   cloudmart-*    labs/cloudmart/{api,web}.yaml
IMAGES=(
  "devopslab/terminal:0.1.0=$ROOT/images/terminal"
  "devopslab/cloudmart-api:0.1.0=$ROOT/apps/cloudmart/api"
  "devopslab/cloudmart-web:0.1.0=$ROOT/apps/cloudmart/web"
)
only="${1:-}"  # optional filter, e.g. `images.sh cloudmart`

for entry in "${IMAGES[@]}"; do
  image="${entry%%=*}" context="${entry#*=}"
  [[ -n "$only" && "$image" != *"$only"* ]] && continue
  info "Building $image (first build takes a few minutes)"
  docker build -t "$image" "$context"
  info "Loading $image into kind cluster '$CLUSTER_NAME'"
  kind load docker-image "$image" --name "$CLUSTER_NAME"
done
