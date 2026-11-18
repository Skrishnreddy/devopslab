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

## Multi-user (future)

Today DevOpsLab is single-user on localhost. The owner label, per-user
namespace prefix and RoleBindings already scope everything by user, so a
hosted multi-user deployment changes the auth provider and the lab
provisioner, not the isolation model.
