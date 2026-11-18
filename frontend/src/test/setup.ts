import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// xterm.js needs canvas support jsdom doesn't have; terminal.test.tsx installs a richer fake.
vi.mock("@xterm/xterm", () => ({
  Terminal: class {
    loadAddon() {} open() {} focus() {} clear() {} write() {} dispose() {}
    getSelection() { return ""; }
    onData() { return { dispose() {} }; }
  },
}));
vi.mock("@xterm/addon-fit", () => ({ FitAddon: class { fit() {} } }));
