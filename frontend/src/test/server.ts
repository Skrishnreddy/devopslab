import { vi } from "vitest";

type Handler = unknown | ((init?: RequestInit) => unknown);
export interface Route { status?: number; body: Handler }

/** Minimal fetch mock keyed by "METHOD /api/v1/path" (query string ignored). */
export function mockApi(routes: Record<string, Route | unknown>) {
  const calls: { key: string; init?: RequestInit }[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const key = `${method} ${url.split("?")[0]}`;
    calls.push({ key, init });
    const hit = routes[key] as Route | undefined;
    const route: Route = hit && typeof hit === "object" && "body" in hit ? hit : { body: hit };
    if (hit === undefined) return new Response(JSON.stringify({ error: { code: "not_found", message: key } }), { status: 404 });
    const body = typeof route.body === "function" ? (route.body as (i?: RequestInit) => unknown)(init) : route.body;
    const status = route.status ?? 200;
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

export const me = { id: 1, username: "admin", role: "admin", session_expires_at: "2030-01-01T00:00:00Z" };

export const kubernetesTrack = {
  id: "kubernetes", name: "Kubernetes", description: "k8s", status: "available", phase: 1,
  progress: { completed: 1, total: 2, percent: 50 },
  modules: [
    { id: "k8s-01-architecture", order: 1, title: "Kubernetes Architecture", level: "beginner", task: "Explore the cluster", skills: [], phase: 5, status: "completed", completed_at: "2026-01-01T00:00:00Z" },
    { id: "k8s-02-pods", order: 2, title: "Pods", level: "beginner", task: "Create and delete Pods", skills: [], phase: 5, status: "not_started", completed_at: null },
  ],
};
export const linuxTrack = { id: "linux", name: "Linux", description: "Shell", status: "planned", phase: 5, modules: [], progress: { completed: 0, total: 0, percent: 0 } };

export const baseRoutes = {
  "GET /api/v1/auth/me": me,
  "GET /api/v1/learn/tracks": [kubernetesTrack, linuxTrack],
  "GET /api/v1/progress/summary": { overall_percent: 50, modules_completed: 1, modules_total: 2, challenges_passed: 0, challenges_failed: 0, hints_used: 0, learning_seconds: 0, skills: [] },
  "GET /api/v1/labs": [],
  "GET /api/v1/activity/recent": [],
  "GET /api/v1/challenges/attempts": [],
  "GET /api/v1/infra/health": {
    overall: "warning", checked_at: new Date().toISOString(),
    components: [
      { id: "colima", name: "Colima", status: "warning", version: "0.8.1", message: "Profile 'devopslab' is not running", remediation: "Run `make up`", details: {}, optional: false },
      { id: "helm", name: "Helm", status: "ok", version: "3.16.4", message: "Installed", remediation: null, details: {}, optional: false },
    ],
  },
  "GET /api/v1/cluster/summary": { connected: false, reason: "No kubeconfig at ~/.kube/devopslab. Run `make up`.", context: "kind-cloudmart" },
};
