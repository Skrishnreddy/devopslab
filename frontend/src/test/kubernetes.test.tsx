import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { baseRoutes, mockApi } from "./server";
import { renderAt } from "./render";

const connected = {
  connected: true, context: "kind-cloudmart", server_version: "v1.31.4",
  nodes: { total: 1, ready: 1, items: [{ name: "cloudmart-control-plane", ready: true, roles: ["control-plane"], version: "v1.31.4", arch: "arm64" }] },
  namespaces: 2, pods: { total: 1, by_phase: { Running: 1 } }, deployments: { total: 1, available: 1 },
};
const routes = {
  ...baseRoutes,
  "GET /api/v1/cluster/summary": connected,
  "GET /api/v1/lab/operation": null,
  "GET /api/v1/cluster/namespaces": [
    { name: "default", status: "Active", age_seconds: 600, lab: false, managed: false },
    { name: "lab-playground", status: "Active", age_seconds: 600, lab: true, managed: true },
  ],
  "GET /api/v1/cluster/pods": [{ namespace: "lab-playground", name: "web-1", phase: "Running", status: "CrashLoopBackOff", ready: "0/1", restarts: 5, node: "w1", age_seconds: 300 }],
  "GET /api/v1/cluster/deployments": [{ namespace: "lab-playground", name: "web", ready: "0/1", up_to_date: 1, available: 0, age_seconds: 300, images: ["web:1"], healthy: false }],
  "GET /api/v1/cluster/services": [{ namespace: "lab-playground", name: "web", type: "ClusterIP", cluster_ip: "10.96.1.1", external_ip: null, ports: "80/TCP", selector: { app: "web" }, age_seconds: 300 }],
  "GET /api/v1/cluster/events": [{ namespace: "lab-playground", type: "Warning", reason: "BackOff", object: "Pod/web-1", message: "Back-off restarting failed container", count: 4, last_seen_seconds: 20 }],
  "GET /api/v1/cluster/pods/lab-playground/web-1": {
    namespace: "lab-playground", name: "web-1", phase: "Running", node: "w1", pod_ip: "10.244.1.5", service_account: "default", labels: {}, age_seconds: 300,
    conditions: [{ type: "Ready", status: "False", reason: "ContainersNotReady", message: null }],
    containers: [{ name: "web", image: "web:1", ready: false, restarts: 5, state: "CrashLoopBackOff", state_detail: "back-off 5m0s", last_state: "Error", last_state_detail: "exit code 1", ports: [], requests: {}, limits: {} }],
    events: [],
  },
  "GET /api/v1/cluster/pods/lab-playground/web-1/logs": { text: "starting\npanic: missing DB_URL\n", body: null },
  "GET /api/v1/cluster/yaml/pod/lab-playground/web-1": { text: "apiVersion: v1\nkind: Pod\n", body: null },
  "GET /api/v1/cluster/yaml/deployment/lab-playground/web": { status: 404, body: { error: { code: "kubernetes_error", message: 'deployments.apps "web" not found' } } },
};

class FakeES {
  static last: FakeES | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) { FakeES.last = this; }
  close() { this.closed = true; }
  emit(msg: object) { this.onmessage?.({ data: JSON.stringify(msg) }); }
}

beforeEach(() => { FakeES.last = null; vi.stubGlobal("EventSource", FakeES); });

describe("kubernetes explorer", () => {
  it("lists every resource type and filters by namespace", async () => {
    const { calls } = mockApi(routes);
    renderAt(<App />, "/kubernetes");
    expect(await screen.findByText("CrashLoopBackOff")).toBeInTheDocument();

    await userEvent.selectOptions(await screen.findByLabelText("Namespace"), "lab-playground");
    await waitFor(() => expect(calls.some((c) => c.url === "/api/v1/cluster/pods?namespace=lab-playground")).toBe(true));

    await userEvent.click(screen.getByRole("tab", { name: "deployments" }));
    expect(await screen.findByText("web:1")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "services" }));
    expect(await screen.findByText("app=web")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "events" }));
    expect(await screen.findByText("Back-off restarting failed container")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "namespaces" }));
    expect(await screen.findByText("lab namespace (resettable)")).toBeInTheDocument();
  });

  it("opens a pod: overview, logs (with live follow) and YAML", async () => {
    mockApi(routes);
    renderAt(<App />, "/kubernetes");
    await userEvent.click(await screen.findByText("web-1"));
    const panel = await screen.findByRole("complementary", { name: "Pod web-1" });
    expect(await within(panel).findByText("back-off 5m0s")).toBeInTheDocument();
    expect(within(panel).getByText(/exit code 1/)).toBeInTheDocument();

    await userEvent.click(within(panel).getByRole("tab", { name: /Logs/ }));
    expect(await within(panel).findByText(/panic: missing DB_URL/)).toBeInTheDocument();
    await userEvent.click(within(panel).getByLabelText("Follow live"));
    await waitFor(() => expect(FakeES.last?.url).toContain("/logs?follow=true"));
    act(() => FakeES.last!.emit({ line: "live line" }));
    expect(await within(panel).findByText("live line")).toBeInTheDocument();
    act(() => FakeES.last!.emit({ end: "The log stream ended (the container stopped or was restarted)." }));
    expect(await within(panel).findByText(/log stream ended/)).toBeInTheDocument();

    await userEvent.click(within(panel).getByRole("tab", { name: /YAML/ }));
    expect(await within(panel).findByText(/kind: Pod/)).toBeInTheDocument();
  });

  it("shows Kubernetes API errors verbatim", async () => {
    mockApi(routes);
    renderAt(<App />, "/kubernetes");
    await userEvent.click(await screen.findByRole("tab", { name: "deployments" }));
    await userEvent.click(await screen.findByLabelText("YAML for deployment web"));
    expect(await screen.findByText('deployments.apps "web" not found')).toBeInTheDocument();
  });

  it("starts the lab when the cluster is down and shows the script output", async () => {
    let op: unknown = null;
    const { calls } = mockApi({
      ...routes,
      "GET /api/v1/cluster/summary": baseRoutes["GET /api/v1/cluster/summary"],
      "GET /api/v1/lab/operation": () => op,
      "POST /api/v1/lab/start": { status: 202, body: () => (op = { action: "start", state: "running", started_at: 0, finished_at: null, exit_code: null, output: ["==> Starting Colima"] }) },
    });
    renderAt(<App />, "/kubernetes");
    await userEvent.click(await screen.findByRole("button", { name: /Start lab/ }));
    expect(calls.some((c) => c.key === "POST /api/v1/lab/start")).toBe(true);
    expect(await screen.findByText("make up: running…")).toBeInTheDocument();
    expect(screen.getByLabelText("Lab output")).toHaveTextContent("==> Starting Colima");
  });

  it("asks before stopping the lab", async () => {
    const { calls } = mockApi({ ...routes, "POST /api/v1/lab/stop": { status: 202, body: { action: "stop", state: "running", started_at: 0, finished_at: null, exit_code: null, output: [] } } });
    renderAt(<App />, "/kubernetes");
    await userEvent.click(await screen.findByRole("button", { name: /Stop lab/ }));
    expect(calls.some((c) => c.key === "POST /api/v1/lab/stop")).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Stop" }));
    expect(calls.some((c) => c.key === "POST /api/v1/lab/stop")).toBe(true);
  });
});
