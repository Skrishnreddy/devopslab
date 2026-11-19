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
  components: string[]; topics: string[]; challenges: string[]; lab: string | null;
}
export interface ChallengeInfo {
  id: string; name: string; difficulty: Level; technology: string; status: Availability; phase: number;
  description: string; skills: string[];
}
export type LabStatus =
  | "not_deployed" | "deploying" | "running" | "starting" | "stopping" | "stopped" | "resetting" | "deleting" | "failed";
export type LabAction = "deploy" | "start" | "stop" | "reset" | "delete";
export interface LabStep { name: string; state: "pending" | "running" | "ok" | "failed"; detail: string; seconds: number | null }
export interface LabRun {
  action: LabAction; state: "running" | "succeeded" | "failed"; error: string | null; failed_step: string | null;
  started_at: number; finished_at: number | null; steps: LabStep[];
}
export interface Lab {
  id: string; kind: string; ref_id: string; url: string | null; status: LabStatus; namespaces: string[];
  last_error: string | null; created_at: string | null; updated_at: string | null; expires_at: string | null;
  operation: LabRun | null;
}
export interface LabUsage {
  cpu_millicores: number; memory_mib: number; pods: number; metrics_error: string | null;
  quota: Record<string, { hard: string; used: string }>;
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

export interface NamespaceInfo { name: string; status: string; age_seconds: number | null; lab: boolean; managed: boolean }
export interface Deployment {
  namespace: string; name: string; ready: string; up_to_date: number; available: number;
  age_seconds: number | null; images: string[]; healthy: boolean;
}
export interface Service {
  namespace: string; name: string; type: string; cluster_ip: string | null; external_ip: string | null;
  ports: string; selector: Record<string, string>; age_seconds: number | null;
}
export interface KubeEvent {
  namespace: string; type: string; reason: string; object: string; message: string; count: number;
  last_seen_seconds: number | null;
}
export interface ContainerInfo {
  name: string; image: string; ready: boolean; restarts: number; state: string; state_detail: string | null;
  last_state: string | null; last_state_detail: string | null; ports: string[];
  requests: Record<string, string>; limits: Record<string, string>;
}
export interface PodDetail {
  namespace: string; name: string; phase: string; node: string | null; pod_ip: string | null;
  service_account: string; labels: Record<string, string>; age_seconds: number | null;
  conditions: { type: string; status: string; reason: string | null; message: string | null }[];
  containers: ContainerInfo[]; events: KubeEvent[];
}
export interface LabOperation {
  action: "start" | "stop"; state: "running" | "succeeded" | "failed"; started_at: number;
  finished_at: number | null; exit_code: number | null; output: string[];
}
export type YamlKind = "pod" | "deployment" | "service" | "namespace" | "node" | "configmap";

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

const enc = encodeURIComponent;
const nsq = (ns?: string) => (ns ? `?namespace=${enc(ns)}` : "");

/** Plain-text endpoints (YAML, logs) still return the JSON error shape on failure. */
async function text(path: string): Promise<string> {
  const res = await fetch(`/api/v1${path}`, { credentials: "same-origin" });
  if (res.ok) return res.text();
  const body = await res.json().catch(() => null);
  const err = body?.error ?? { code: "http_error", message: res.statusText || `HTTP ${res.status}` };
  if (res.status === 401) unauthorizedListeners.forEach((l) => l());
  throw new ApiError(res.status, err.code, err.message);
}

/** Live log lines over server-sent events. Returns a function that stops following. */
export function followLogs(ns: string, name: string, container: string,
  onLine: (line: string) => void, onEnd: (reason: string) => void): () => void {
  const es = new EventSource(`/api/v1/cluster/pods/${enc(ns)}/${enc(name)}/logs?follow=true&tail=100&container=${enc(container)}`);
  es.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (typeof msg.line === "string") onLine(msg.line);
    if (msg.end) { onEnd(msg.end); es.close(); }
  };
  es.onerror = () => { onEnd("Live logs disconnected."); es.close(); };
  return () => es.close();
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
  lab: (id: string) => req<Lab>(`/labs/${enc(id)}`),
  deployLab: (refId: string) => req<Lab>("/labs", { method: "POST", body: JSON.stringify({ ref_id: refId }) }),
  labDo: (id: string, action: "start" | "stop" | "reset" | "extend") =>
    req<Lab>(`/labs/${enc(id)}/${action}`, { method: "POST" }),
  deleteLab: (id: string) => req<Lab>(`/labs/${enc(id)}`, { method: "DELETE" }),
  labUsage: (id: string) => req<LabUsage>(`/labs/${enc(id)}/usage`),
  attempts: (limit = 5) => req<Attempt[]>(`/challenges/attempts?limit=${limit}`),
  progress: () => req<ProgressSummary>("/progress/summary"),
  activity: (limit = 5) => req<ActivityItem[]>(`/activity/recent?limit=${limit}`),
  settings: () => req<AppSettings>("/settings"),
  namespaces: () => req<NamespaceInfo[]>("/cluster/namespaces"),
  deployments: (ns?: string) => req<Deployment[]>(`/cluster/deployments${nsq(ns)}`),
  services: (ns?: string) => req<Service[]>(`/cluster/services${nsq(ns)}`),
  events: (ns?: string) => req<KubeEvent[]>(`/cluster/events${nsq(ns)}`),
  pod: (ns: string, name: string) => req<PodDetail>(`/cluster/pods/${enc(ns)}/${enc(name)}`),
  yaml: (kind: YamlKind, name: string, ns?: string) =>
    text(`/cluster/yaml/${kind}/${ns ? `${enc(ns)}/` : ""}${enc(name)}`),
  logs: (ns: string, name: string, container: string, tail = 500, previous = false) =>
    text(`/cluster/pods/${enc(ns)}/${enc(name)}/logs?container=${enc(container)}&tail=${tail}&previous=${previous}`),
  labOperation: () => req<LabOperation | null>("/lab/operation"),
  labAction: (action: "start" | "stop") => req<LabOperation>(`/lab/${action}`, { method: "POST" }),
  terminalProfiles: () => req<TerminalProfile[]>("/terminal/profiles"),
  terminalSessions: () => req<TerminalSession[]>("/terminal/sessions"),
  openTerminal: (profile: TerminalProfileId) =>
    req<TerminalSession>("/terminal/sessions", { method: "POST", body: JSON.stringify({ profile }) }),
  closeTerminal: (id: string) => req<void>(`/terminal/sessions/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

/** WebSocket URL for a terminal session; same origin, so the session cookie goes with it. */
export const terminalStreamUrl = (id: string, loc: Location = window.location) =>
  `${loc.protocol === "https:" ? "wss" : "ws"}://${loc.host}/api/v1/terminal/sessions/${encodeURIComponent(id)}/stream`;
