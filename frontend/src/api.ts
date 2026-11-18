export type Level = "beginner" | "intermediate" | "advanced";

export interface Module {
  id: string; order: number; title: string; level: Level; task: string; completed: boolean;
}
export interface Track {
  id: string; name: string; status: "available" | "planned"; modules: Module[];
  progress: { completed: number; total: number; percent: number };
}
export interface ClusterSummary {
  connected: boolean;
  reason?: string;
  context?: string;
  nodes?: { total: number; ready: number; items: { name: string; ready: boolean; roles: string[]; version: string }[] };
  namespaces?: number;
  pods?: { total: number; by_phase: Record<string, number> };
  deployments?: { total: number; available: number };
}
export interface Pod {
  namespace: string; name: string; phase: string; status: string; ready: string; restarts: number; node: string | null;
}
export interface Incident { id: string; title: string; severity: "low" | "medium" | "high" | "critical" }
export interface Project {
  id: string; name: string; lab: string; stage: number; status: "available" | "planned";
  summary: string; components: string[]; topics: string[]; incidents: Incident[];
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText);
  return res.json() as Promise<T>;
}

export const api = {
  cluster: () => req<ClusterSummary>("/api/cluster/summary"),
  pods: (ns?: string) => req<Pod[]>(`/api/cluster/pods${ns ? `?namespace=${encodeURIComponent(ns)}` : ""}`),
  tracks: () => req<Track[]>("/api/learn/tracks"),
  setComplete: (id: string, completed: boolean) =>
    req(`/api/learn/modules/${id}/complete`, { method: "POST", body: JSON.stringify({ completed }) }),
  projects: () => req<Project[]>("/api/engineer/projects"),
};
