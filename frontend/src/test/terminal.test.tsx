import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { terminalStreamUrl } from "../api";
import { baseRoutes, mockApi } from "./server";
import { renderAt } from "./render";

// xterm needs a real canvas/layout; the page logic is what we test here.
const { terminals, FakeTerm } = vi.hoisted(() => {
  const terminals: InstanceType<typeof FakeTerm>[] = [];
  class FakeTerm {
    cols = 80; rows = 24; written: (string | Uint8Array)[] = []; dataCb: ((d: string) => void) | null = null;
    selection = "";
    clear = vi.fn();
    constructor() { terminals.push(this); }
    loadAddon() {}
    open() {}
    focus() {}
    getSelection() { return this.selection; }
    write(d: string | Uint8Array) { this.written.push(d); }
    onData(cb: (d: string) => void) { this.dataCb = cb; return { dispose() {} }; }
    dispose() {}
  }
  return { terminals, FakeTerm };
});
vi.mock("@xterm/xterm", () => ({ Terminal: FakeTerm }));
vi.mock("@xterm/addon-fit", () => ({ FitAddon: class { fit() {} } }));

class FakeWS {
  static OPEN = 1;
  static all: FakeWS[] = [];
  readyState = 0; sent: string[] = []; binaryType = "";
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onclose: ((e: { code: number; reason: string }) => void) | null = null;
  constructor(public url: string) { FakeWS.all.push(this); }
  send(d: string) { this.sent.push(d); }
  close() {}
  serverOpen() { this.readyState = 1; this.onmessage?.({ data: JSON.stringify({ type: "status", state: "connected" }) }); }
  serverClose(reason: string) {
    this.onmessage?.({ data: JSON.stringify({ type: "status", state: "closed", reason }) });
    this.readyState = 3; this.onclose?.({ code: 1000, reason: "" });
  }
}

const profiles = [
  { id: "linux", name: "Linux", available: true, description: "Ubuntu shell" },
  { id: "kubernetes", name: "Kubernetes", available: true, description: "kubectl" },
  { id: "docker", name: "Docker", available: false, phase: 2, description: "Planned" },
];
const session = (id: string, profile = "kubernetes") => ({
  id, profile, status: "ready", error: null, created_at: 0, last_activity: 0, idle_timeout_seconds: 1800, max_seconds: 14400,
});

beforeEach(() => {
  terminals.length = 0;
  FakeWS.all = [];
  vi.stubGlobal("WebSocket", FakeWS);
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
});

describe("terminal page", () => {
  it("builds a same-origin WebSocket URL", () => {
    expect(terminalStreamUrl("t-1", { protocol: "http:", host: "127.0.0.1:5173" } as Location))
      .toBe("ws://127.0.0.1:5173/api/v1/terminal/sessions/t-1/stream");
    expect(terminalStreamUrl("t-1", { protocol: "https:", host: "lab" } as Location)).toMatch(/^wss:/);
  });

  it("opens a sandbox, bridges keystrokes and resize, and shows the connection state", async () => {
    const { calls } = mockApi({
      ...baseRoutes,
      "GET /api/v1/terminal/profiles": profiles,
      "GET /api/v1/terminal/sessions": [],
      "POST /api/v1/terminal/sessions": { status: 201, body: session("t-abc") },
    });
    renderAt(<App />, "/terminal");
    expect(await screen.findByText(/Planned · Phase 2/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Docker/ })).not.toBeInTheDocument();

    await userEvent.click(await screen.findByRole("button", { name: /Kubernetes/ }));
    const post = calls.find((c) => c.key === "POST /api/v1/terminal/sessions");
    expect(JSON.parse(String(post?.init?.body))).toEqual({ profile: "kubernetes" });

    await waitFor(() => expect(FakeWS.all).toHaveLength(1));
    const ws = FakeWS.all[0];
    expect(ws.url).toContain("/api/v1/terminal/sessions/t-abc/stream");
    expect(screen.getByText("Connecting…")).toBeInTheDocument();
    act(() => ws.serverOpen());
    expect(await screen.findByText("Connected")).toBeInTheDocument();

    act(() => terminals[0].dataCb?.("ls\r"));
    expect(ws.sent.map((s) => JSON.parse(s))).toContainEqual({ type: "input", data: "ls\r" });

    act(() => ws.onmessage?.({ data: new TextEncoder().encode("hello").buffer }));
    expect(new TextDecoder().decode(terminals[0].written[terminals[0].written.length - 1] as Uint8Array)).toBe("hello");

    await userEvent.click(screen.getByRole("button", { name: /Clear/ }));
    expect(terminals[0].clear).toHaveBeenCalled();

    act(() => ws.serverClose("Closed after being idle"));
    expect(await screen.findByText("Closed after being idle")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Reconnect/ }));
    expect(FakeWS.all).toHaveLength(2);
  });

  it("reattaches to existing sessions and closes a tab", async () => {
    const { calls } = mockApi({
      ...baseRoutes,
      "GET /api/v1/terminal/profiles": profiles,
      "GET /api/v1/terminal/sessions": [session("t-1", "linux"), session("t-2")],
      "DELETE /api/v1/terminal/sessions/t-1": { status: 204, body: null },
    });
    renderAt(<App />, "/terminal");
    expect(await screen.findByRole("tab", { name: /Linux 1/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Kubernetes 1/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Close Linux terminal" }));
    await waitFor(() => expect(screen.queryByRole("tab", { name: /Linux 1/ })).not.toBeInTheDocument());
    expect(calls.some((c) => c.key === "DELETE /api/v1/terminal/sessions/t-1")).toBe(true);
    expect(screen.getByRole("tab", { name: /Kubernetes 1/ })).toHaveAttribute("aria-selected", "true");
  });

  it("shows why a sandbox couldn't start", async () => {
    mockApi({
      ...baseRoutes,
      "GET /api/v1/terminal/profiles": profiles,
      "GET /api/v1/terminal/sessions": [],
      "POST /api/v1/terminal/sessions": { status: 409, body: { error: { code: "pod_failed", message: "Sandbox pod failed: ErrImageNeverPull. Run `make images` to build and load it." } } },
    });
    renderAt(<App />, "/terminal");
    await userEvent.click(await screen.findByRole("button", { name: /Linux/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("make images");
  });
});
