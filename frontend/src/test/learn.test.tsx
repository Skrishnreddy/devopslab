import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { baseRoutes, mockApi } from "./server";
import { renderAt } from "./render";

const exercise = (over: object = {}) => ({
  id: "first-pod", title: "Run your first Pod", kind: "practice", instructions: "Create a Pod named `web`.\n\n    kubectl run web --image=nginx:1.27-alpine",
  expected_output: "web   1/1   Running", hint: "Use `kubectl run`.", has_setup: false, checks: ["Pod web is Running and Ready"],
  passed: false, last: null, ...over,
});
const lesson = {
  id: "k8s-02-pods", order: 2, title: "Pods", level: "beginner", task: "Create and delete Pods", skills: [], track_id: "kubernetes",
  track_name: "Kubernetes", status: "started", namespace: "lab-playground",
  lesson: {
    concept: "A **Pod** is the smallest thing Kubernetes runs.", use_case: "Debugging.", architecture: "Pod web\n  container",
    commands: [{ command: "kubectl get pods", explanation: "List Pods." }],
    yaml: [{ title: "A Pod manifest", explanation: "Same as run.", content: "kind: Pod\n" }],
  },
  exercises: [exercise(), exercise({ id: "bad-image", title: "Troubleshoot: ImagePullBackOff", kind: "troubleshooting", has_setup: true, checks: ["Pod shop is Ready"] })],
  quiz: { questions: [{ question: "What is a Pod?", options: ["A node", "Containers sharing a network"] }, { question: "Bare Pod node fails?", options: ["Recreated", "Gone"] }], best_percent: null, passed: false, pass_percent: 70 },
};
const fail = { passed: false, at: "2026-11-19T10:00:00Z", module_status: "started", results: [{ description: "Pod web is Running and Ready", passed: false, observed: "0 of 1 pods with app=web ready: web (ImagePullBackOff)" }] };
const pass = { ...fail, passed: true, results: [{ description: "Pod web is Running and Ready", passed: true, observed: "1 of 1 pods with app=web ready: web (Running)" }] };

describe("Learn: lessons", () => {
  it("links modules that have a lesson and marks the rest planned", async () => {
    mockApi(baseRoutes);
    renderAt(<App />, "/learn");
    expect(await screen.findByRole("link", { name: "Open lesson Kubernetes Architecture" })).toHaveAttribute("href", "/learn/k8s-01-architecture");
    expect(screen.getByText("lesson planned")).toBeInTheDocument();
  });

  it("renders every part of a lesson and hides solutions until asked", async () => {
    const { calls } = mockApi({ ...baseRoutes, "GET /api/v1/learn/modules/k8s-02-pods": lesson,
      "GET /api/v1/learn/modules/k8s-02-pods/exercises/first-pod/solution": { solution: "kubectl run web --image=nginx:1.27-alpine --labels=app=web" } });
    renderAt(<App />, "/learn/k8s-02-pods");
    expect(await screen.findByRole("heading", { name: "02 · Pods" })).toBeInTheDocument();
    for (const t of ["Concept", "When you'll use it", "How it fits together", "Commands", "YAML: A Pod manifest", "Quiz"]) expect(screen.getByText(t)).toBeInTheDocument();
    expect(screen.getByText("Pod", { selector: "strong" })).toBeInTheDocument();
    const ex = screen.getByRole("region", { name: "Exercise Run your first Pod" });
    expect(within(ex).getByText("kubectl run web --image=nginx:1.27-alpine", { selector: "pre" })).toBeInTheDocument();
    expect(within(ex).queryByRole("button", { name: /Set up/ })).toBeNull();
    expect(within(screen.getByRole("region", { name: "Exercise Troubleshoot: ImagePullBackOff" })).getByRole("button", { name: /Set up/ })).toBeInTheDocument();
    expect(within(ex).queryByText(/--labels=app=web/)).toBeNull();
    await userEvent.click(within(ex).getByRole("button", { name: "Show solution" }));
    expect(await within(ex).findByText(/--labels=app=web/)).toBeInTheDocument();
    expect(calls.some((c) => c.key.endsWith("/solution"))).toBe(true);
    await userEvent.click(within(ex).getByRole("button", { name: /Hint/ }));
    expect(within(ex).getByText("kubectl run", { selector: "code" })).toBeInTheDocument();
  });

  it("Check shows what the cluster really has, then passes", async () => {
    let n = 0;
    mockApi({ ...baseRoutes, "GET /api/v1/learn/modules/k8s-02-pods": lesson,
      "POST /api/v1/learn/modules/k8s-02-pods/exercises/first-pod/check": { body: () => (n++ === 0 ? fail : pass) } });
    renderAt(<App />, "/learn/k8s-02-pods");
    const ex = await screen.findByRole("region", { name: "Exercise Run your first Pod" });
    await userEvent.click(within(ex).getByRole("button", { name: /Check/ }));
    expect(await within(ex).findByText("Not yet")).toBeInTheDocument();
    expect(within(ex).getByText("0 of 1 pods with app=web ready: web (ImagePullBackOff)")).toBeInTheDocument();
    await userEvent.click(within(ex).getByRole("button", { name: /Check/ }));
    expect(await within(ex).findByText("All checks passed")).toBeInTheDocument();
  });

  it("set up and errors are shown, never swallowed", async () => {
    mockApi({ ...baseRoutes, "GET /api/v1/learn/modules/k8s-02-pods": lesson,
      "POST /api/v1/learn/modules/k8s-02-pods/exercises/bad-image/setup": { body: { namespace: "lab-playground", output: ["pod/shop created"] } },
      "POST /api/v1/learn/modules/k8s-02-pods/exercises/bad-image/check": { status: 503, body: { error: { code: "cluster_unreachable", message: "No kubeconfig at ~/.kube/devopslab. Run `make up`." } } } });
    renderAt(<App />, "/learn/k8s-02-pods");
    const ex = await screen.findByRole("region", { name: "Exercise Troubleshoot: ImagePullBackOff" });
    await userEvent.click(within(ex).getByRole("button", { name: /Set up/ }));
    expect(await within(ex).findByLabelText("kubectl output")).toHaveTextContent("pod/shop created");
    await userEvent.click(within(ex).getByRole("button", { name: /Check/ }));
    expect(await within(ex).findByRole("alert")).toHaveTextContent("Run `make up`");
  });

  it("quiz is graded by the server and explains each answer", async () => {
    const { calls } = mockApi({ ...baseRoutes, "GET /api/v1/learn/modules/k8s-02-pods": lesson,
      "POST /api/v1/learn/modules/k8s-02-pods/quiz": { score: 1, total: 2, percent: 50, passed: false, module_status: "started",
        results: [{ correct: true, answer: 1, explanation: "They share a network." }, { correct: false, answer: 1, explanation: "Nothing recreates a bare Pod." }] } });
    renderAt(<App />, "/learn/k8s-02-pods");
    const quiz = await screen.findByRole("form", { name: "Quiz" });
    const submit = within(quiz).getByRole("button", { name: "Submit answers" });
    expect(submit).toBeDisabled();
    await userEvent.click(within(quiz).getByLabelText("Containers sharing a network"));
    await userEvent.click(within(quiz).getByLabelText("Recreated"));
    await userEvent.click(submit);
    expect(await within(quiz).findByRole("status")).toHaveTextContent("1/2 (50%). You need 70% to pass.");
    expect(within(quiz).getByText(/Nothing recreates a bare Pod/)).toBeInTheDocument();
    await waitFor(() => expect(JSON.parse(calls.find((c) => c.key.endsWith("/quiz"))!.init!.body as string)).toEqual({ answers: [1, 0] }));
  });

  it("a module without a lesson shows the API's message", async () => {
    mockApi({ ...baseRoutes, "GET /api/v1/learn/modules/k8s-09-x": { status: 404, body: { error: { code: "not_found", message: "Module 'k8s-09-x' has no lesson yet (Planned)" } } } });
    renderAt(<App />, "/learn/k8s-09-x");
    expect(await screen.findByRole("alert")).toHaveTextContent("has no lesson yet (Planned)");
  });
});
