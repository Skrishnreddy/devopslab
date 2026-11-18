# Security policy

DevOpsLab runs real shells and talks to a real Kubernetes cluster, so we take
security reports seriously.

## Supported versions

Only the latest release and `main` receive fixes while the project is pre-1.0.

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's private reporting:
**Security → Report a vulnerability** on this repository. Include steps to
reproduce, affected versions and impact. We aim to acknowledge within 5 days
and to agree a disclosure date with you.

## Design guarantees we treat as vulnerabilities if broken

- The API, UI and terminals listen on 127.0.0.1 only.
- Every API route except health and login requires a session.
- Terminals never run on the host and never mount the host Docker socket.
- Learner credentials are never cluster-admin.
- Lab reset only deletes namespaces it owns.
- The AI Teacher only proposes commands; nothing runs without the learner's approval.
- Secrets are redacted before reaching any model; nothing is sent to an external AI
  provider without explicit consent.

Details: [docs/security/terminal.md](docs/security/terminal.md) and
[docs/security/lab-isolation.md](docs/security/lab-isolation.md).

## Secrets

Never commit API keys, passwords, private keys, kubeconfigs or `.env` files.
CI runs gitleaks on every push; run `make secrets-scan` locally before pushing.
