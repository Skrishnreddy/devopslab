# Architecture

```
 Browser (127.0.0.1:5173)
   React + TS + Tailwind ── xterm.js (Stage 3)
            │  /api (Vite proxy, HTTP + WebSocket)
            ▼
 FastAPI (127.0.0.1:8000)
   routers/cluster   read-only cluster view (kubernetes client)
   routers/learn     tracks, modules, progress  ── SQLite
   routers/engineer  projects, lab deploy/reset ── services/lab_engine
   routers/terminal  WebSocket ⇄ exec into sandbox pods (Stage 3)
            │  ~/.kube/devopslab, context kind-cloudmart
            ▼
 Colima VM (vz, 4 CPU / 6 GB)
   kind cluster "cloudmart": 1 control plane + 2 workers
     ingress-nginx, metrics-server
     devopslab-system     lab internals
     devopslab-terminal   terminal sandbox pods
     cloudmart, …         resettable project namespaces (Stage 4+)
```

## Principles

1. **Loopback only.** Backend and Vite bind to 127.0.0.1. Ingress host ports
   are bound to 127.0.0.1 in `infra/kind/cluster.yaml`.
2. **No host shell.** The terminal never spawns a process on the Mac.
3. **Resettable by namespace.** Breaking a lab never means rebuilding the
   cluster.
4. **Content as data.** Tracks, projects and challenges are YAML, so adding a
   module or incident doesn't need code changes.

## Stage 3: terminal design

Each terminal tab is a WebSocket from xterm.js to
`/api/terminal/{profile}/ws`. The backend creates (or reuses) a pod in
`devopslab-terminal` and bridges the socket to the Kubernetes exec stream with
the Python client's `stream()`. Nothing runs on the host.

| Tab        | Pod image             | Access                                                         |
|------------|-----------------------|----------------------------------------------------------------|
| Linux      | Ubuntu + systemd      | Its own container only; systemctl/journalctl work inside it    |
| Kubernetes | kubectl, helm, k9s    | ServiceAccount `lab-learner`: full rights in lab namespaces, read-only cluster-wide, no access to `devopslab-*` or `kube-system` writes |
| Docker     | Docker CLI + rootless dind sidecar | Talks to the sidecar daemon, never to Colima's Docker socket |

Pods get CPU/memory limits (about 250m / 256Mi each) and are deleted after
30 idle minutes.

## Stage 4 and 6: labs and challenges

- `labs/<id>/kustomization.yaml` is a project's known-good state.
- `labs/challenges/*.yaml` define incidents: `inject` (patches applied after a
  reset), `verify` (checks for "resolved"), `hints` (progressive), and
  `root_cause` (shown after you pass).
- Flow: reset lab → inject fault → you investigate in the terminal → hints on
  request (counted) → verify → record result in SQLite.

## Stage 7: AI hints

Static hints from the challenge YAML come first. Ollama is optional and later:
it gets the incident, your recent commands and the hint ladder, and is told to
nudge rather than give the fix.
