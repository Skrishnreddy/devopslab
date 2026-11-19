# CloudMart

A small online shop you deploy, explore, break and restore. It is the Engineer
Mode project for Phase 4 and the base for later troubleshooting scenarios.

```
browser ──> ingress-nginx (http://localhost:8080)
              ├── /      ─> web  (React storefront on nginx, 2 replicas)
              └── /api   ─> api  (FastAPI, 2 replicas) ─┬─> postgres (StatefulSet, 1Gi volume)
                                                         └─> redis    (carts)
```

| Component | Image | Source |
|---|---|---|
| web | `devopslab/cloudmart-web:0.1.0` | [`apps/cloudmart/web`](../../apps/cloudmart/web) |
| api | `devopslab/cloudmart-api:0.1.0` | [`apps/cloudmart/api`](../../apps/cloudmart/api) |
| postgres | `postgres:16.6-alpine` | upstream |
| redis | `redis:7.4.1-alpine` | upstream |

The two DevOpsLab images are built locally by `make images` (part of `make up`)
and loaded into kind; they are never pulled from a registry
(`imagePullPolicy: Never`).

## Use it

1. `make up` (once), then open **Projects → CloudMart → Deploy** in DevOpsLab.
2. Watch the steps: render manifests, create namespaces, generate secrets,
   apply manifests, wait until ready. When it says *running*, open
   <http://localhost:8080>, add something to the cart and place an order.
3. Explore it in **Kubernetes** (namespace `lab-cloudmart`) or a Kubernetes
   terminal, where the `lab-learner` account can edit this namespace.

| Action | What happens |
|---|---|
| Stop | Every Deployment and StatefulSet is scaled to 0. Volumes and data stay. |
| Start | The manifests are applied again (replicas come back) and readiness is awaited. |
| Reset | `lab-cloudmart` is deleted (including the database) and deployed again from these manifests, with a new database password. Running it twice gives the same result. |
| Delete | `lab-cloudmart` and everything in it is removed. |
| Extend time | A running lab stops automatically 4 hours after it was started; Extend gives it 4 hours from now. |

If a step fails, the lab is marked *failed* and the UI shows the step and the
real `kubectl` error, plus the pods that aren't ready and why
(e.g. `ErrImageNeverPull` if the images weren't built: run `make images`).

## Guardrails

Applied with the lab (`guardrails.yaml`): ResourceQuota (requests 2 CPU / 2Gi,
limits 4 CPU / 3Gi, 20 pods, 3 PVCs, no NodePorts or LoadBalancers), LimitRange
defaults, a NetworkPolicy that only admits traffic from this namespace,
ingress-nginx and DevOpsLab terminals, and Pod Security `baseline`. See
[lab isolation](../../docs/security/lab-isolation.md).

## Develop the app

```bash
cd apps/cloudmart/api && pip install -r requirements.txt pytest httpx && pytest -q
cd apps/cloudmart/web && npm ci && npm run build
make images            # rebuild both images and load them into kind; then Reset the lab
```

The Helm chart for CloudMart is **Planned** (Kustomize today).
