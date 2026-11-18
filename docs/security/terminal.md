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
   - *Kubernetes*: kubectl and helm. Uses ServiceAccount `lab-learner`
     (`infra/manifests/terminal/rbac.yaml`): the built-in `edit` role in the
     lab namespace `lab-playground` only, the built-in `view` role elsewhere
     (which excludes Secrets), and read-only nodes, namespaces, PVs, storage
     classes and metrics. **No cluster-admin, ever.** No writes outside lab
     namespaces, no Secrets outside the lab, no RBAC objects. Phase 4 adds
     per-lab namespaces with their own RoleBindings.
   - *Docker/DevOps* (Phase 2b, planned): needs a Docker engine per session.
     The host or Colima Docker socket is **never mounted**. Rootless
     docker-in-docker still needs relaxed pod security, so this profile is
     held back until that trade-off is decided.
5. **Network**: a default-deny NetworkPolicy in `devopslab-terminal`
   (`infra/manifests/terminal/networkpolicy.yaml`). Every terminal may reach
   cluster DNS. The Kubernetes profile may also reach the API server (TCP
   6443) and pods in resettable lab namespaces. No inbound traffic and no
   internet. Known limit: the 6443 rule is by port, because the control
   plane address isn't fixed in kind.
6. **Authentication**: WebSocket upgrade requires a valid session cookie and
   an `Origin` in the allowlist. Each session id is bound to its user and is
   not guessable (128-bit random). A session belongs to the user who opened
   it; any other user gets 404.
7. **Timeouts**: idle 30 min without input, absolute 4 h (also enforced by the
   pod's `activeDeadlineSeconds`); both close the socket and delete the pod.
   At most 4 terminals per user. A reaper deletes orphaned pods on backend
   start, and all terminal pods are deleted when the backend stops. Closing a
   browser tab only detaches: reopen the Terminal page to get a new shell in
   the same sandbox, or use **End session** to delete it.
8. **Exposure**: the WebSocket is served only by the backend on 127.0.0.1.
   No NodePort, LoadBalancer or Ingress for terminals.
9. **Audit**: session open/close, profile and close reason are recorded in
   `terminal_sessions`.
   Keystrokes and output are not stored.

## Acceptance tests (Phase 2)

- Pod spec generated for each profile matches rules 3–5 (unit test).
- WebSocket without a session or with a foreign Origin is rejected (API test).
- From the Kubernetes terminal: `kubectl auth can-i '*' '*' --all-namespaces`
  is `no`; `kubectl get secrets -n kube-system` is forbidden (cluster test).
- From the Linux terminal: no service account token is mounted and no
  internet access (cluster test).
- From the Docker terminal (Phase 2b): `docker info` reports the sandbox
  daemon, not Colima's (cluster test).
- Idle timeout deletes the pod (cluster test with shortened timeout).
