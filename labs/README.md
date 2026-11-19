# Labs

Known-good Kubernetes manifests for Engineer Mode projects, one folder per lab,
deployed with `kubectl apply -k`. Today: [CloudMart](cloudmart/README.md).

```
labs/<lab-id>/
  kustomization.yaml
  lab.yaml            # url and generated secrets; read by the engine, not applied
  namespace.yaml      # labelled devopslab.io/resettable: "true"
  guardrails.yaml     # quota, limit range, network policy, learner RoleBinding
  ...
```

The lab engine (`backend/app/providers/labs.py`, run by `lab_service.py`) deploys,
stops, starts, resets and deletes a lab as a list of named steps. It only ever
deletes namespaces that the lab's own manifests label resettable (never
`kube-system`, `ingress-nginx`, `default` or `devopslab-*`). Secrets listed in
`lab.yaml` are generated with random values in the cluster at deploy time.

Adding a lab: create the folder, add `lab: <lab-id>` to a project in
`content/projects/`, and put any locally built image in `infra/scripts/images.sh`
(a test checks they match). See
[docs/security/lab-isolation.md](../docs/security/lab-isolation.md).

Troubleshooting scenarios live in `content/challenges/`.
