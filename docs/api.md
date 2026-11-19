# API contracts (v1)

Base path `/api/v1`. JSON everywhere. Served on 127.0.0.1 only.

## Conventions

- **Auth**: every endpoint except `GET /health` and `POST /auth/login`
  requires the `devopslab_session` cookie (HttpOnly, SameSite=Strict). Missing
  or expired → `401`.
- **CSRF**: state-changing requests must carry an `Origin` in the allowlist
  (`DEVOPSLAB_ALLOWED_ORIGINS`); otherwise `403`.
- **Errors** always use one shape:
  ```json
  {"error": {"code": "cluster_unreachable", "message": "Human readable", "detail": {}}}
  ```
- **Infrastructure honesty**: endpoints that read infrastructure never fall back
  to cached or sample data. If the source is down they say so
  (`status: "error"` or HTTP `503`).
- **Planned features** are listed by `GET /features` with `status: "planned"`
  and have no endpoints until built.

## Phase 1 endpoints

| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/health` | | `{status, version}` liveness, no auth |
| POST | `/auth/login` | `{token}` | `204`, sets cookie. `401` bad token |
| POST | `/auth/logout` | | `204`, clears session |
| GET | `/auth/me` | | `{id, username, role, session_expires_at}` |
| GET | `/features` | | `[{id, name, status: available\|planned, phase}]` |
| GET | `/infra/health` | | `{overall, checked_at, components: [{id, name, status: ok\|warning\|error\|missing, version, message, remediation}]}` |
| GET | `/cluster/summary` | | `{connected, reason?, context, server_version, nodes{total,ready,items[]}, namespaces, pods{total,by_phase}, deployments{total,available}}` |
| GET | `/cluster/pods` | `?namespace=` | `[{namespace,name,phase,status,ready,restarts,node,age_seconds}]`; `503` if unreachable |
| GET | `/learn/tracks` | | `[Track]` with per-user `progress` |
| GET | `/learn/tracks/{track_id}` | | `Track` |
| PUT | `/learn/modules/{module_id}/progress` | `{status: not_started\|started\|completed}` | `{module_id, status, completed_at}` |
| GET | `/projects` | | `[Project]` from content catalog, with `status` |
| GET | `/labs` | | every deployable lab: `[Lab]`, `status: not_deployed` when it has never been deployed |
| GET | `/labs/{id}` | | `Lab`: `{id, kind, ref_id, url, status, namespaces, last_error, created_at, updated_at, expires_at, operation}`. `status`: `not_deployed`, `deploying`, `running`, `starting`, `stopping`, `stopped`, `resetting`, `deleting`, `failed`. `operation` (in memory, last one): `{action, state: running\|succeeded\|failed, error, failed_step, steps: [{name, state: pending\|running\|ok\|failed, detail, seconds}]}` |
| POST | `/labs` | `{ref_id}` | `202 Lab` (deploying); `404` unknown lab, `409` already deployed |
| POST | `/labs/{id}/{start\|stop\|reset}` | | `202 Lab`; `409` if busy or not allowed from the current status |
| POST | `/labs/{id}/extend` | | `202 Lab` with a new `expires_at` (running labs only) |
| DELETE | `/labs/{id}` | | `202 Lab` (deleting); the lab returns to `not_deployed` when done |
| GET | `/labs/{id}/usage` | | `{cpu_millicores, memory_mib, pods, quota: {name: {hard, used}}, metrics_error}`; `404` if not deployed |
| GET | `/challenges/attempts` | `?limit=` | recent `[ChallengeAttempt]` |
| GET | `/progress/summary` | | `{overall_percent, modules_completed, modules_total, challenges_passed, challenges_failed, hints_used, learning_seconds, skills[]}` |
| GET | `/activity/recent` | `?kind=&limit=` | `[{kind, ref_id, title, at}]` |
| GET | `/settings` | | `{environment{data_dir, kube_context, cluster_name, colima_profile}, ai{provider, enabled}}` |

## Later phases (contract drafts)

| Phase | Method | Path | Notes |
|---|---|---|---|
| 2 | GET | `/terminal/profiles` | linux, kubernetes, docker |
| 2 | POST | `/terminal/sessions` | `{profile: linux\|kubernetes\|docker}` → session (waits until the sandbox is ready; docker first starts the Docker VM); 409 on limit or pod failure, 503 if the cluster is down |
| 2 | GET | `/terminal/sessions` | list own sessions |
| 2 | DELETE | `/terminal/sessions/{id}` | close + delete pod |
| 2 | WS | `/terminal/sessions/{id}/stream` | foreign Origin refused at the handshake (HTTP 403); then closes with 4401 (not logged in), 4404 (not found) or 4409 (not ready). Client sends JSON `{type:"input",data}` / `{type:"resize",cols,rows}`; server sends binary output and JSON `{type:"status",state,reason}` |
| 3 | GET | `/cluster/{namespaces,deployments,services,events}` | `?namespace=`; columns match `kubectl get` |
| 3 | GET | `/cluster/pods/{ns}/{name}` | containers (state, last state, restarts), conditions, events |
| 3 | GET | `/cluster/yaml/{kind}/[{ns}/]{name}` | `text/plain`; kinds pod, deployment, service, configmap, namespace, node (never Secret); managedFields stripped |
| 3 | GET | `/cluster/pods/{ns}/{name}/logs` | `?container=&tail=&previous=&follow=`; text, or SSE `{line}` … `{end}` when following (max 30 min) |
| 3 | GET | `/lab/operation` | last start/stop: state, exit code, last 300 output lines |
| 3 | POST | `/lab/{start\|stop}` | `202`; runs `infra/scripts/up.sh` / `down.sh` (same as `make up` / `make down`); `409` if one is running |
|   |   | Kubernetes API errors | passed through verbatim: `{"error":{"code":"kubernetes_error","message":"pods \"x\" not found","detail":{"status":404}}}`; unreachable cluster is `503 cluster_unreachable` |
| 5 | POST | `/learn/exercises/{id}/check` | runs validation in the lab |
| 6 | POST | `/challenges/{id}/start` | creates lab + injects fault |
| 6 | POST | `/challenges/attempts/{id}/hints` | reveals next hint (max 3) |
| 6 | POST | `/challenges/attempts/{id}/validate` | runs validation conditions |
| 6 | POST | `/challenges/attempts/{id}/solution` | marks `solution_viewed`, returns resolution |
| 9 | | `/ai/*` | AI Teacher: status, models, conversations (SSE), command proposals, assessments. See `docs/ai-teacher.md` |
