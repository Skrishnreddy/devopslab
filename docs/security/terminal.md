# Terminal security boundaries

The terminal (Phase 2) gives a real interactive shell. It must never give a
shell on the host machine. This document is the contract the implementation
and its tests must meet.

## Trust model

| Party                  | Trusted? | Why                                                |
|------------------------|----------|----------------------------------------------------|
| Host (your Mac)        | Yes      | Runs the backend; must be protected from labs      |
| Backend process        | Yes      | Holds the admin kubeconfig; never forwards it      |
| Learner input          | No       | Anything typed may be malicious or destructive     |
| Lab content / images   | Partly   | Reviewed in PRs, but run as if untrusted           |

## Rules

1. **No host processes.** The backend never spawns a shell, `kubectl exec`
   subprocess, or PTY on the host for a learner. It bridges the WebSocket to
   the Kubernetes exec API (`pods/exec` stream) of a sandbox pod.
2. **Disposable sandbox pods** in namespace `devopslab-terminal`, one per
   session, created on open and deleted on close or timeout.
3. **Pod hardening** (enforced by Pod Security Admission `restricted` where
   the profile allows it, and by tests on the generated pod spec):
   - `runAsNonRoot: true`, `runAsUser: 1000`, `allowPrivilegeEscalation: false`
   - `capabilities: drop: [ALL]`; `seccompProfile: RuntimeDefault`
   - `readOnlyRootFilesystem: true` with an `emptyDir` home (size-limited)
   - limits: `cpu: 500m`, `memory: 512Mi`, `ephemeral-storage: 1Gi`
   - `automountServiceAccountToken: false` except the Kubernetes profile
4. **Profiles**
   - *Linux*: Ubuntu-based image, non-root. Learners practise `ps`, `top`,
     `journalctl` etc. inside the container. Exercises that need real systemd
     run in a dedicated systemd lab (Phase 5), never privileged by default.
   - *Kubernetes*: kubectl, helm, k9s. Uses ServiceAccount
     `lab-learner-<session>` bound by RoleBinding to the selected lab
     namespace(s) only, plus a read-only ClusterRole for nodes, namespaces and
     events. **No cluster-admin, ever.** No access to `kube-system` writes,
     `devopslab-*` namespaces, Secrets outside the lab, or RBAC objects unless
     a module explicitly grants a scoped Role.
   - *Docker/DevOps*: Docker CLI talks to a rootless `docker:dind-rootless`
     sidecar inside the same pod. The host or Colima Docker socket is **never
     mounted**.
5. **Network**: a default-deny NetworkPolicy in `devopslab-terminal`; egress
   allowed only to cluster DNS, the Kubernetes API (Kubernetes profile), and
   the lab namespace. Internet egress is off unless a module turns it on
   (e.g. image pulls through the dind sidecar).
6. **Authentication**: WebSocket upgrade requires a valid session cookie and
   an `Origin` in the allowlist. Each session id is bound to its user and is
   not guessable (128-bit random).
7. **Timeouts**: idle 30 min, absolute 4 h; both close the socket and delete
   the pod. A reaper deletes orphaned pods on backend start.
8. **Exposure**: the WebSocket is served only by the backend on 127.0.0.1.
   No NodePort, LoadBalancer or Ingress for terminals.
9. **Audit**: session open/close, profile, lab and duration are recorded.
   Keystrokes and output are not stored.

## Acceptance tests (Phase 2)

- Pod spec generated for each profile matches rules 3–5 (unit test).
- WebSocket without a session or with a foreign Origin is rejected (API test).
- From the Kubernetes terminal: `kubectl auth can-i '*' '*' --all-namespaces`
  is `no`; `kubectl get secrets -n kube-system` is forbidden (cluster test).
- From the Docker terminal: `docker info` reports the sidecar daemon, not
  Colima's (cluster test).
- Idle timeout deletes the pod (cluster test with shortened timeout).
