# Contributing to DevOpsLab

Thanks for helping! There are two ways to contribute: **content** (modules,
projects, troubleshooting scenarios) and **code**.

## Ground rules

- Never commit secrets, kubeconfigs, `.env` files or personal data.
- Never add fake output, hardcoded metrics or buttons that don't work. If a
  feature isn't built yet, mark it `status: planned` with its `phase`.
- Learner-facing access must stay least-privilege: no cluster-admin, no host
  shell, no host Docker socket.
- Container images must support `linux/arm64` (Apple Silicon) and should
  support `linux/amd64`.

## Adding content (no Python or React needed)

Content lives in `content/` and is validated against JSON Schemas in
`content/schemas/`. Point your editor at the schema for autocompletion, e.g.
in VS Code add `# yaml-language-server: $schema=../../schemas/challenge.schema.json`
at the top of a challenge file.

| What | Where | Schema |
|---|---|---|
| Learning track and modules | `content/tracks/<id>.yaml` | `track.schema.json` |
| Engineer Mode project | `content/projects/<id>.yaml` | `project.schema.json` |
| Troubleshooting scenario | `content/challenges/<tech>/<id>.yaml` | `challenge.schema.json` |
| Lesson for a module | `content/lessons/<track>/<module-id>.yaml` | `lesson.schema.json` |

### Writing a lesson

A lesson's `id` is the module id it belongs to. It needs a concept, a use
case, an architecture sketch, commands, optional YAML examples, at least one
exercise (one of them `kind: troubleshooting`) and at least three quiz
questions. See `content/lessons/kubernetes/k8s-02-pods.yaml`.

Exercises run in the `lab-playground` namespace, where the Kubernetes
terminal works. Each one has:

- `checks`: what **Check** verifies against the real cluster, read-only.
  Types: `exists`, `absent`, `field` (a dotted path such as
  `spec.containers[0].image` equals a value), `pods_ready` (by label
  selector), `rollout_ready`, `endpoints`, and `answer` (a ConfigMap key must
  equal a real cluster fact, which is never shown to the learner).
- `setup` (optional): manifests applied before a troubleshooting exercise.
  Only Pods, Deployments, ReplicaSets, Services and ConfigMaps, and no
  `namespace` field; everything goes to `lab-playground`.
- `cleanup`: every object the exercise creates, including its setup. **Reset**
  deletes these and applies the setup again. A test checks that every
  object a check looks at is in `cleanup`.
- `expected_output`, an optional `hint`, and a `solution` that is shown only
  when the learner asks for it.

Images must be pinned tags that run under Pod Security `baseline`.

A scenario can only be `status: available` once it has an initial state,
injection steps, symptoms, exactly three hints (direction → resource →
approach), validation checks, root cause, resolution and reset. See
`content/challenges/kubernetes/readiness-probe-failure.yaml` for a full
example.

Check your changes with `make test-backend` (it validates all content).

## Code

```bash
make install        # backend venv + frontend packages
make dev            # API on :8000, UI on :5173
make test           # everything CI runs
make schemas        # regenerate JSON Schemas after changing content models
```

- Backend: FastAPI + SQLAlchemy. Schema changes need an Alembic migration:
  `cd backend && .venv/bin/alembic revision --autogenerate -m "..."`.
  A test fails if models and migrations drift.
- Providers (`backend/app/providers/`) are interfaces; add a new runtime,
  cluster, terminal or AI backend by implementing one and selecting it in
  `registry.py`.
- Frontend: React + TypeScript + Tailwind. Every page handles loading, empty
  and error states and shows API errors to the user.
- Add tests with every feature: backend unit/API tests in `backend/tests`,
  frontend tests in `frontend/src/test`.

## Pull requests

1. Fork, branch from `main`, keep PRs focused.
2. `make test` passes locally.
3. Update docs and `CHANGELOG.md` under *Unreleased*.
4. Describe what you changed and how you tested it.

By contributing you agree your work is licensed under Apache-2.0.
