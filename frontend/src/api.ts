// Typed client for /api/v1. Shapes mirror docs/api.md.
export type Level = "beginner" | "intermediate" | "advanced";
export type Availability = "available" | "planned";
export type HealthStatus = "ok" | "warning" | "error" | "missing";
export type ModuleStatus = "not_started" | "started" | "completed";

export interface Me { id: number; username: string; role: string; session_expires_at: string }
export interface Feature { id: string; name: string; status: Availability; phase: number }
export interface Component {
  id: string; name: string; status: HealthStatus; version: string | null; message: string;
  remediation: string | null; details: Record<string, string | number>; optional: boolean;
}
export interface InfraHealth { overall: HealthStatus; checked_at: string; components: Component[] }
export interface NodeInfo { name: string; ready: boolean; roles: string[]; version: string; arch: string }
export interface ClusterSummary {
  connected: boolean; reason?: string; context: string; server_version?: string;
  nodes?: { total: number; ready: number; items: NodeInfo[] };
  namespaces?: number;
  pods?: { total: number; by_phase: Record<string, number> };
  deployments?: { total: number; available: number };
}
export interface Pod {
  namespace: string; name: string; phase: string; status: string; ready: string;
  restarts: number; node: string | null; age_seconds: number | null;
}
export interface Module {
  id: string; order: number; title: string; level: Level; task: string; skills: string[]; phase: number;
  status: ModuleStatus; completed_at: string | null;
}
export interface Track {
  id: string; name: string; description: string; status: Availability; phase: number; modules: Module[];
  progress: { completed: number; total: number; percent: number };
}
export interface Project {
  id: string; name: string; status: Availability; phase: number; summary: string;
  components: string[]; topics: string[]; challenges: string[];
}
export interface ChallengeInfo {
  id: string; name: string; difficulty: Level; technology: string; status: Availability; phase: number;
  description: string; skills: string[];
}
export interface Lab {
  id: string; kind: string; ref_id: string; status: string; namespaces: string[]; last_error: string | null;
  created_at: string; updated_at: string; expires_at: string | null;
}
export interface Attempt {
  id: number; challenge_id: string; name: string; status: string; hints_used: number;
  started_at: string; finished_at: string | null;
}
export interface ProgressSummary {
  overall_percent: number; modules_completed: number; modules_total: number; challenges_passed: number;
  challenges_failed: number; hints_used: number; learning_seconds: number; skills: string[];
}
export interface ActivityItem { kind: string; ref_id: string; title: string; at: string }
export interface AppSettings {
  environment: Record<string, string>; session_hours: number;
  ai: { enabled: boolean; provider: string; base_url: string; local: boolean; status: Availability; phase: number };
}

export type TerminalProfileId = "linux" | "kubernetes" | "docker";
export interface TerminalProfile {
  id: TerminalProfileId; name: string; available: boolean; description: string; phase?: number;
}
export interface TerminalSession {
  id: string; profile: TerminalProfileId; status: "starting" | "ready" | "closed" | "failed"; error: string | null;
  created_at: number; last_activity: number; idle_timeout_seconds: number; max_seconds: number;
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

type Listener = () => void;
const unauthorizedListeners = new Set<Listener>();
export const onUnauthorized = (fn: Listener) => {
  unauthorizedListeners.add(fn);
  return () => { unauthorizedListeners.delete(fn); };
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    credentials: "same-origin",
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error ?? { code: "http_error", message: res.statusText || `HTTP ${res.status}` };
    if (res.status === 401 && !path.startsWith("/auth/login")) unauthorizedListeners.forEach((l) => l());
    throw new ApiError(res.status, err.code, err.message);
  }
  return body as T;
}

export const api = {
  login: (token: string) => req<void>("/auth/login", { method: "POST", body: JSON.stringify({ token }) }),
  logout: () => req<void>("/auth/logout", { method: "POST" }),
  me: () => req<Me>("/auth/me"),
  features: () => req<Feature[]>("/features"),
  infra: () => req<InfraHealth>("/infra/health"),
  cluster: () => req<ClusterSummary>("/cluster/summary"),
  pods: (ns?: string) => req<Pod[]>(`/cluster/pods${ns ? `?namespace=${encodeURIComponent(ns)}` : ""}`),
  tracks: () => req<Track[]>("/learn/tracks"),
  setProgress: (id: string, status: ModuleStatus) =>
    req(`/learn/modules/${encodeURIComponent(id)}/progress`, { method: "PUT", body: JSON.stringify({ status }) }),
  projects: () => req<Project[]>("/projects"),
  challenges: () => req<ChallengeInfo[]>("/challenges"),
  labs: () => req<Lab[]>("/labs"),
  attempts: (limit = 5) => req<Attempt[]>(`/challenges/attempts?limit=${limit}`),
  progress: () => req<ProgressSummary>("/progress/summary"),
  activity: (limit = 5) => req<ActivityItem[]>(`/activity/recent?limit=${limit}`),
  settings: () => req<AppSettings>("/settings"),
  terminalProfiles: () => req<TerminalProfile[]>("/terminal/profiles"),
  terminalSessions: () => req<TerminalSession[]>("/terminal/sessions"),
  openTerminal: (profile: TerminalProfileId) =>
    req<TerminalSession>("/terminal/sessions", { method: "POST", body: JSON.stringify({ profile }) }),
  closeTerminal: (id: string) => req<void>(`/terminal/sessions/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

/** WebSocket URL for a terminal session; same origin, so the session cookie goes with it. */
export const terminalStreamUrl = (id: string, loc: Location = window.location) =>
  `${loc.protocol === "https:" ? "wss" : "ws"}://${loc.host}/api/v1/terminal/sessions/${encodeURIComponent(id)}/stream`;
