# Labs

Each Engineer Mode project is a folder here, deployed with `kubectl apply -k`.

```
labs/<lab-id>/
  kustomization.yaml     # known-good state of the project
  namespace.yaml         # labelled devopslab.io/resettable: "true"
  ...manifests
```

The lab engine (`backend/app/services/lab_engine.py`) resets a lab by deleting
only its resettable namespaces and re-applying the kustomization. It refuses to
touch any namespace without that label, so `kube-system`, `ingress-nginx` and
the lab's own system namespaces are never wiped.

`cloudmart/` is filled in during Stage 4. `challenges/` holds incident
definitions for the Stage 6 challenge engine.
