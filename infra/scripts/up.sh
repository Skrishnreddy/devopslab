#!/usr/bin/env bash
# Stage 1: start the Colima VM and the kind cluster, then install cluster add-ons.
# Idempotent: re-running skips whatever already exists.
# shellcheck source=SCRIPTDIR/lib.sh
source "$(dirname "$0")/lib.sh"
for t in colima docker kind kubectl helm; do need "$t"; done

save_docker_context
trap restore_docker_context EXIT

if colima status -p "$COLIMA_PROFILE" >/dev/null 2>&1; then
  info "Colima profile '$COLIMA_PROFILE' already running"
else
  info "Starting Colima ($COLIMA_CPUS CPU, ${COLIMA_MEMORY} GB RAM, ${COLIMA_DISK} GB disk)"
  colima start -p "$COLIMA_PROFILE" --cpu "$COLIMA_CPUS" --memory "$COLIMA_MEMORY" \
    --disk "$COLIMA_DISK" --vm-type vz --mount-type virtiofs
fi

mkdir -p "$(dirname "$KUBECONFIG")"
if kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
  info "kind cluster '$CLUSTER_NAME' already exists"
else
  info "Creating kind cluster '$CLUSTER_NAME' (1 control plane + 2 workers)"
  kind create cluster --name "$CLUSTER_NAME" --image "$KIND_NODE_IMAGE" \
    --config "$ROOT/infra/kind/cluster.yaml" --wait 120s
fi
kind export kubeconfig --name "$CLUSTER_NAME" >/dev/null

# After a VM restart the API server needs a moment; applying too early fails validation.
info "Waiting for the Kubernetes API server"
for _ in $(seq 1 90); do
  k get --raw=/readyz >/dev/null 2>&1 && break
  sleep 2
done
k get --raw=/readyz >/dev/null || die "The Kubernetes API server didn't become ready in 3 minutes. Check: make status"
k wait --for=condition=Ready nodes --all --timeout=180s >/dev/null

info "Applying lab namespaces and terminal sandbox policies"
k apply -f "$ROOT/infra/manifests/base/"
k apply -f "$ROOT/infra/manifests/terminal/"

info "Installing ingress-nginx (kind provider)"
# Pinned. Upstream ingress-nginx is retired; fine for a local lab, Gateway API comes later.
k apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/kind/deploy.yaml
k -n ingress-nginx rollout status deploy/ingress-nginx-controller --timeout=180s

info "Installing metrics-server (needed for kubectl top and HPA)"
helm --kube-context "$KCTX" repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/ >/dev/null 2>&1 || true
helm --kube-context "$KCTX" repo update metrics-server >/dev/null
helm --kube-context "$KCTX" upgrade --install metrics-server metrics-server/metrics-server \
  -n kube-system --set 'args={--kubelet-insecure-tls}' \
  --set resources.requests.memory=64Mi --wait

"$ROOT/infra/scripts/images.sh"

info "Monitoring stays OFF to save RAM. Turn it on later with: make monitoring-on"
info "Cluster ready. KUBECONFIG=$KUBECONFIG"
k get nodes -o wide
