# Lab isolation

A **lab** is one running copy of a project, module exercise or challenge. Labs
are what learners break and reset.

## Model

| Lab kind   | Isolation unit                      | Example                    |
|------------|-------------------------------------|----------------------------|
| module     | one namespace `lab-<user>-<module>` | Pods exercise              |
| challenge  | one namespace `lab-<user>-<chal>`   | CrashLoopBackOff scenario  |
| project    | 1..n namespaces `lab-<user>-<proj>-*` | CloudMart                |
| node-level | disposable kind cluster (planned)   | Node NotReady, kubeadm     |

Challenges that need node-level faults (Node NotReady) run in a separate,
short-lived kind cluster rather than breaking the shared cluster.

## Guarantees

1. **Labels mark ownership.** Every namespace the lab engine creates has
   `devopslab.io/managed=true`, `devopslab.io/resettable=true`,
   `devopslab.io/lab-id=<id>` and `devopslab.io/owner=<user-id>`.
2. **Only labelled namespaces are deleted.** Reset and delete operate on
   namespaces selected by `devopslab.io/lab-id=<id>`, and refuse if none
   match. `kube-system`, `ingress-nginx`, `devopslab-*` are never touched.
3. **Per-namespace guardrails** applied on create: ResourceQuota (CPU 1,
   memory 1Gi, pods 20, PVCs 3), LimitRange defaults, and a NetworkPolicy
   that denies ingress from other `lab-*` namespaces owned by another user.
4. **Scoped credentials.** A lab's terminal ServiceAccount has a RoleBinding in
   that lab's namespaces only (see terminal.md).
5. **Idempotent reset.** Reset = delete labelled namespaces (wait for
   termination) → re-apply known-good manifests → wait for readiness →
   re-inject the challenge fault if any. Running reset twice yields the same
   state. Every step is recorded; a failure marks the lab `failed` with the
   step and the Kubernetes error shown to the user. Nothing is silently retried
   forever.
6. **Timeouts and cleanup.** Labs have `expires_at` (default 4 h idle). A
   cleanup job stops expired labs (scale to zero) and deletes labs idle for
   24 h. Users see the countdown.
7. **Resource accounting.** Lab status includes live CPU/memory from
   metrics-server summed over its namespaces.

## What Phase 4 implements

The design above is the target. This is what runs today, for the CloudMart
project lab (`labs/cloudmart`, engine in `backend/app/providers/labs.py`):

| Guarantee | Today |
|---|---|
| 1. Labels | `lab-cloudmart` carries `managed`, `resettable` and `lab-id`. The `owner` label and per-user namespace prefix are **Planned** with multi-user; DevOpsLab is single-user, and the API still checks that the lab row belongs to the logged-in user. |
| 2. What gets deleted | Reset and delete render the lab's manifests and delete only the namespaces those manifests label `resettable=true`, minus `default`, `kube-*`, `ingress-nginx` and `devopslab-*`. If none qualify, nothing is touched. |
| 3. Guardrails | ResourceQuota requests 2 CPU / 2Gi, limits 4 CPU / 3Gi, 20 pods, 3 PVCs, 0 NodePorts and LoadBalancers (CloudMart needs more than the 1 CPU / 1Gi above); LimitRange defaults; NetworkPolicy admitting only same-namespace, ingress-nginx and DevOpsLab terminal traffic; Pod Security `baseline`. |
| 4. Credentials | `lab-learner` gets `edit` in `lab-cloudmart` through a RoleBinding shipped with the lab. The database password is generated randomly in the cluster (`kubectl apply` over stdin, never on a command line) and is never written to git, the database or logs. Reset creates a new one. |
| 5. Reset | Delete namespaces (waits for termination) → create namespaces → generate secrets → apply manifests → wait for every Deployment and StatefulSet rollout. Every step is recorded with its duration; a failure stops there, marks the lab `failed` and stores `<step>: <kubectl error>` with the pods that aren't ready. One operation per lab at a time (`409` otherwise). Labs caught mid-operation by a restart are marked failed with that reason. |
| 6. Expiry | A running lab expires 4 h after it was last (re)started or extended, and is then **stopped** (scaled to 0), never deleted. Deleting long-idle labs is **Planned**. |
| 7. Usage | `GET /labs/{id}/usage`: live CPU/memory from metrics-server and quota used/hard, summed over the lab's namespaces. |

## Multi-user (future)

Today DevOpsLab is single-user on localhost. The owner label, per-user
namespace prefix and RoleBindings already scope everything by user, so a
hosted multi-user deployment changes the auth provider and the lab
provisioner, not the isolation model.
