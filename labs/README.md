# Labs

Known-good Kubernetes manifests for Engineer Mode projects, one folder per lab,
deployed with `kubectl apply -k`. Filled in from Phase 4 (CloudMart).

```
labs/<lab-id>/
  kustomization.yaml
  namespace.yaml      # labelled devopslab.io/resettable: "true"
  ...
```

The lab provisioner (`backend/app/providers/labs.py`) resets a lab by deleting
only namespaces that carry the resettable label (never `kube-system`,
`ingress-nginx` or `devopslab-*`) and re-applying the kustomization. See
[docs/security/lab-isolation.md](../docs/security/lab-isolation.md).

Troubleshooting scenarios live in `content/challenges/`.
