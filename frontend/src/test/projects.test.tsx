import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { baseRoutes, mockApi } from "./server";
import { renderAt } from "./render";

const project = {
  id: "cloudmart", name: "CloudMart", status: "available", phase: 4, summary: "Shop", components: ["React"],
  topics: ["Ingress"], challenges: [], lab: "cloudmart",
};
const planned = { ...project, id: "gitops", name: "GitOps", status: "planned", phase: 10, lab: null };
const base = {
  id: "cloudmart", kind: "project", ref_id: "cloudmart", url: "http://localhost:8080", namespaces: [] as string[],
  last_error: null as string | null, created_at: null, updated_at: null, expires_at: null as string | null, operation: null as unknown,
};
const notDeployed = { ...base, status: "not_deployed" };
const steps = (states: string[]) =>
  ["render manifests", "create namespaces", "generate secrets", "apply manifests", "wait until ready"].map((name, i) => ({
    name, state: states[i] ?? "pending", detail: states[i] === "failed" ? 'deployment.apps/api isn\'t ready: ErrImageNeverPull' : "", seconds: states[i] === "ok" ? 1.2 : null,
  }));

function setup(lab: object, extra: Record<string, unknown> = {}) {
  return mockApi({
    ...baseRoutes, "GET /api/v1/projects": [project, planned], "GET /api/v1/labs": [lab], "GET /api/v1/labs/cloudmart": lab, ...extra,
  });
}

describe("Projects: CloudMart lab", () => {
  it("deploys and shows the steps as they run", async () => {
    const deploying = { ...base, status: "deploying", operation: { action: "deploy", state: "running", error: null, failed_step: null, started_at: 1, finished_at: null, steps: steps(["ok", "running"]) } };
    const { calls } = setup(notDeployed, { "POST /api/v1/labs": { status: 202, body: deploying } });
    renderAt(<App />, "/projects");
    const lab = await screen.findByRole("region", { name: "cloudmart lab" });
    expect(within(lab).getByText("not deployed")).toBeInTheDocument();
    await userEvent.click(within(lab).getByRole("button", { name: /Deploy/ }));
    expect(JSON.parse(calls.find((c) => c.key === "POST /api/v1/labs")!.init!.body as string)).toEqual({ ref_id: "cloudmart" });
    const list = await within(lab).findByLabelText("Lab steps");
    expect(within(list).getByText("deploy: in progress…")).toBeInTheDocument();
    expect(within(list).getAllByRole("listitem").map((li) => li.dataset.state)).toEqual(["ok", "running", "pending", "pending", "pending"]);
    expect(within(lab).queryByRole("button")).toBeNull();  // nothing to click while busy
    expect(screen.queryByRole("region", { name: /gitops lab/ })).toBeNull();
  });

  it("running lab: open link, time left, usage and controls", async () => {
    const running = { ...base, status: "running", namespaces: ["lab-cloudmart"], expires_at: new Date(Date.now() + 90 * 60_000).toISOString() };
    setup(running, {
      "GET /api/v1/labs/cloudmart/usage": { cpu_millicores: 42, memory_mib: 310, pods: 7, metrics_error: null, quota: { pods: { hard: "20", used: "7" }, "limits.memory": { hard: "3Gi", used: "1792Mi" } } },
    });
    renderAt(<App />, "/projects");
    const lab = await screen.findByRole("region", { name: "cloudmart lab" });
    expect(within(lab).getByRole("link", { name: /Open localhost:8080/ })).toHaveAttribute("href", "http://localhost:8080");
    expect(within(lab).getByText(/1h 30m left|1h 29m left/)).toBeInTheDocument();
    const usage = await within(lab).findByLabelText("Lab usage");
    expect(usage).toHaveTextContent("42m");
    expect(usage).toHaveTextContent("1792Mi / 3Gi");
    for (const name of [/Stop/, /Extend time/, /Reset/, /Delete/]) expect(within(lab).getByRole("button", { name })).toBeInTheDocument();
    expect(within(lab).queryByRole("button", { name: /Start/ })).toBeNull();
  });

  it("reset asks first and warns that data is lost", async () => {
    const running = { ...base, status: "running", namespaces: ["lab-cloudmart"] };
    const { calls } = setup(running, {
      "GET /api/v1/labs/cloudmart/usage": { cpu_millicores: 0, memory_mib: 0, pods: 0, metrics_error: "metrics-server: not ready", quota: {} },
      "POST /api/v1/labs/cloudmart/reset": { status: 202, body: { ...running, status: "resetting" } },
    });
    renderAt(<App />, "/projects");
    const lab = await screen.findByRole("region", { name: "cloudmart lab" });
    await userEvent.click(within(lab).getByRole("button", { name: /Reset/ }));
    const dialog = within(lab).getByRole("alertdialog", { name: "Confirm reset" });
    expect(dialog).toHaveTextContent("including its database");
    expect(calls.some((c) => c.key === "POST /api/v1/labs/cloudmart/reset")).toBe(false);
    await userEvent.click(within(dialog).getByRole("button", { name: "Reset lab" }));
    await waitFor(() => expect(calls.some((c) => c.key === "POST /api/v1/labs/cloudmart/reset")).toBe(true));
    expect(await within(lab).findByText("resetting")).toBeInTheDocument();
  });

  it("a failed reset shows the failing step and the real error", async () => {
    const failed = { ...base, status: "failed", namespaces: ["lab-cloudmart"], last_error: "wait until ready: deployment.apps/api isn't ready: ErrImageNeverPull",
      operation: { action: "reset", state: "failed", error: "x", failed_step: "wait until ready", started_at: 1, finished_at: 2, steps: steps(["ok", "ok", "ok", "ok", "failed"]) } };
    setup(failed);
    renderAt(<App />, "/projects");
    const lab = await screen.findByRole("region", { name: "cloudmart lab" });
    expect(within(lab).getByText("failed")).toBeInTheDocument();
    expect(within(lab).getByText("reset: failed at “wait until ready”")).toBeInTheDocument();
    expect(within(lab).getByText(/ErrImageNeverPull/)).toBeInTheDocument();
    for (const name of [/Start/, /Stop/, /Reset/, /Delete/]) expect(within(lab).getByRole("button", { name })).toBeInTheDocument();
  });

  it("after a restart, the stored error is still shown", async () => {
    setup({ ...base, status: "failed", namespaces: ["lab-cloudmart"], last_error: "interrupted: DevOpsLab restarted during the operation." });
    renderAt(<App />, "/projects");
    expect(await screen.findByText(/interrupted: DevOpsLab restarted/)).toBeInTheDocument();
    expect(screen.getByText("The last operation failed")).toBeInTheDocument();
  });

  it("an API refusal is shown, not swallowed", async () => {
    setup(notDeployed, { "POST /api/v1/labs": { status: 409, body: { error: { code: "lab_busy", message: "The lab is busy (deploying). Wait for it to finish." } } } });
    renderAt(<App />, "/projects");
    const lab = await screen.findByRole("region", { name: "cloudmart lab" });
    await userEvent.click(within(lab).getByRole("button", { name: /Deploy/ }));
    expect(await within(lab).findByRole("alert")).toHaveTextContent("The lab is busy");
  });
});
