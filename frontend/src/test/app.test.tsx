import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { ApiError, api, onUnauthorized } from "../api";
import { baseRoutes, mockApi } from "./server";
import { renderAt } from "./render";

describe("api client", () => {
  it("parses the backend error shape", async () => {
    mockApi({ "GET /api/v1/cluster/pods": { status: 503, body: { error: { code: "cluster_unreachable", message: "API down" } } } });
    await expect(api.pods()).rejects.toMatchObject({ status: 503, code: "cluster_unreachable", message: "API down" });
  });

  it("notifies listeners on 401", async () => {
    mockApi({ "GET /api/v1/labs": { status: 401, body: { error: { code: "unauthorized", message: "Log in" } } } });
    const listener = vi.fn();
    const off = onUnauthorized(listener);
    await expect(api.labs()).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledOnce();
    off();
  });
});

describe("auth", () => {
  it("sends unauthenticated users to the login page", async () => {
    mockApi({ "GET /api/v1/auth/me": { status: 401, body: { error: { code: "unauthorized", message: "Log in" } } } });
    renderAt(<App />, "/");
    expect(await screen.findByLabelText("Login token")).toBeInTheDocument();
  });

  it("logs in with the token from the URL fragment", async () => {
    let loggedIn = false;
    const { calls } = mockApi({
      ...baseRoutes,
      "GET /api/v1/auth/me": () => (loggedIn ? baseRoutes["GET /api/v1/auth/me"] : undefined),
      "POST /api/v1/auth/login": { status: 204, body: () => { loggedIn = true; return null; } },
    });
    window.location.hash = "#token=abc123";
    renderAt(<App />, "/login");
    await waitFor(() => expect(calls.some((c) => c.key === "POST /api/v1/auth/login")).toBe(true));
    const login = calls.find((c) => c.key === "POST /api/v1/auth/login")!;
    expect(JSON.parse(String(login.init?.body))).toEqual({ token: "abc123" });
    expect(window.location.hash).toBe("");
  });
});

describe("dashboard", () => {
  it("shows real infrastructure status and an offline cluster honestly", async () => {
    mockApi(baseRoutes);
    renderAt(<App />, "/");
    expect(await screen.findByText("Profile 'devopslab' is not running")).toBeInTheDocument();
    expect(screen.getAllByText("make up", { selector: "code" }).length).toBeGreaterThan(0);
    expect(await screen.findByText("The lab cluster isn't reachable.")).toBeInTheDocument();
    expect(screen.getByText(/No labs running/)).toBeInTheDocument();
    expect(screen.getByText(/No challenges attempted/)).toBeInTheDocument();
  });

  it("renders cluster counts straight from the API", async () => {
    mockApi({
      ...baseRoutes,
      "GET /api/v1/cluster/summary": {
        connected: true, context: "kind-cloudmart", server_version: "v1.31.4",
        nodes: { total: 3, ready: 2, items: [] }, namespaces: 9,
        pods: { total: 17, by_phase: { Running: 15, Pending: 2 } }, deployments: { total: 6, available: 5 },
      },
    });
    renderAt(<App />, "/");
    const card = (await screen.findByText("Kubernetes cluster")).closest("section")!;
    await waitFor(() => expect(within(card).getByText("2/3")).toBeInTheDocument());
    expect(within(card).getByText("9")).toBeInTheDocument();
    expect(within(card).getByText("17")).toBeInTheDocument();
    expect(within(card).getByText("2 not running")).toBeInTheDocument();
    expect(within(card).getByText("5 available")).toBeInTheDocument();
  });

  it("continues with the first unfinished module", async () => {
    mockApi(baseRoutes);
    renderAt(<App />, "/");
    expect(await screen.findByText("Create and delete Pods")).toBeInTheDocument();
  });
});

describe("navigation", () => {
  it("has the 14 sections from the spec, with planned ones marked", async () => {
    mockApi(baseRoutes);
    renderAt(<App />, "/");
    const nav = await screen.findByRole("navigation", { name: "Main" });
    const links = within(nav).getAllByRole("link");
    expect(links.map((l) => l.textContent?.replace("planned", ""))).toEqual([
      "Dashboard", "Learn", "Linux", "Docker", "Kubernetes", "Terraform", "Jenkins", "Ansible",
      "Monitoring", "DevSecOps", "Projects", "Troubleshooting", "Terminal", "Settings",
    ]);
    expect(within(links[12]).getByText("planned")).toBeInTheDocument();
  });
});

describe("learn", () => {
  it("advances a module's status through the API", async () => {
    const { calls } = mockApi({ ...baseRoutes, "PUT /api/v1/learn/modules/k8s-02-pods/progress": { module_id: "k8s-02-pods", status: "started" } });
    renderAt(<App />, "/learn");
    await userEvent.click(await screen.findByRole("button", { name: /Pods: Not started/ }));
    const put = calls.find((c) => c.key === "PUT /api/v1/learn/modules/k8s-02-pods/progress");
    expect(JSON.parse(String(put?.init?.body))).toEqual({ status: "started" });
  });

  it("shows save failures instead of hiding them", async () => {
    mockApi({ ...baseRoutes, "PUT /api/v1/learn/modules/k8s-02-pods/progress": { status: 500, body: { error: { code: "internal_error", message: "disk full" } } } });
    renderAt(<App />, "/learn");
    await userEvent.click(await screen.findByRole("button", { name: /Pods: Not started/ }));
    expect(await screen.findByText("disk full")).toBeInTheDocument();
  });
});
