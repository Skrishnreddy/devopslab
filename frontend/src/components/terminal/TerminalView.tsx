import { useEffect, useRef, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { ClipboardCopy, ClipboardPaste, Eraser, RotateCw, X } from "lucide-react";
import { terminalStreamUrl, type TerminalSession } from "../../api";

type Conn = { state: "connecting" | "connected" | "closed"; reason?: string };

const THEME = {
  background: "#0b0f17", foreground: "#d6dbe4", cursor: "#38bdf8", selectionBackground: "#334155",
};

/** One xterm.js instance bridged to the session's WebSocket. Stays mounted while hidden. */
export function TerminalView({ session, active, onClose }: {
  session: TerminalSession; active: boolean; onClose: () => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const term = useRef<Terminal | null>(null);
  const fit = useRef<FitAddon | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const [conn, setConn] = useState<Conn>({ state: "connecting" });
  const [attempt, setAttempt] = useState(0);
  const [note, setNote] = useState<string | null>(null);

  const send = (msg: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(msg));
  };
  const sendSize = () => {
    if (!term.current || !fit.current || !host.current?.offsetParent) return;
    fit.current.fit();
    send({ type: "resize", cols: term.current.cols, rows: term.current.rows });
  };

  // xterm instance: created once per session.
  useEffect(() => {
    const t = new Terminal({
      cursorBlink: true, fontSize: 13, scrollback: 5000, theme: THEME,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
    });
    const f = new FitAddon();
    t.loadAddon(f);
    t.open(host.current!);
    term.current = t;
    fit.current = f;
    const data = t.onData((d) => send({ type: "input", data: d }));
    const ro = new ResizeObserver(() => sendSize());
    ro.observe(host.current!);
    return () => { ro.disconnect(); data.dispose(); t.dispose(); term.current = null; };
  }, [session.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // WebSocket: reconnects when `attempt` changes.
  useEffect(() => {
    setConn({ state: "connecting" });
    const sock = new WebSocket(terminalStreamUrl(session.id));
    sock.binaryType = "arraybuffer";
    ws.current = sock;
    let closedReason: string | undefined;
    sock.onmessage = (ev) => {
      if (typeof ev.data === "string") {
        const msg = JSON.parse(ev.data);
        if (msg.type === "status" && msg.state === "connected") {
          setConn({ state: "connected" });
          sendSize();
          term.current?.focus();
        } else if (msg.type === "status" && msg.state === "closed") {
          closedReason = msg.reason;
        }
      } else {
        term.current?.write(new Uint8Array(ev.data as ArrayBuffer));
      }
    };
    sock.onclose = (ev) => {
      const reason = closedReason ?? (ev.reason || (ev.code === 1006 ? "Connection lost" : "Disconnected"));
      setConn({ state: "closed", reason });
      term.current?.write(`\r\n\x1b[33m[${reason}]\x1b[0m\r\n`);
    };
    return () => { sock.onclose = null; sock.close(); };
  }, [session.id, attempt]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (active) { sendSize(); term.current?.focus(); } }, [active]); // eslint-disable-line react-hooks/exhaustive-deps

  const flash = (msg: string) => { setNote(msg); setTimeout(() => setNote(null), 2000); };
  const copy = async () => {
    const text = term.current?.getSelection() ?? "";
    if (!text) return flash("Select text first");
    try { await navigator.clipboard.writeText(text); flash("Copied"); } catch { flash("Clipboard blocked by the browser"); }
  };
  const paste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) send({ type: "input", data: text });
      term.current?.focus();
    } catch { flash("Clipboard blocked: use ⌘V in the terminal"); }
  };

  const dot = conn.state === "connected" ? "bg-ok" : conn.state === "connecting" ? "bg-warn" : "bg-bad";
  const btn = "inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-ink-300 hover:bg-ink-800 hover:text-white disabled:opacity-40";

  return (
    <div className={active ? "flex h-full flex-col" : "hidden"} data-testid={`terminal-${session.id}`}>
      <div className="flex flex-wrap items-center gap-2 border-b border-ink-700 px-3 py-1.5">
        <span className={`h-2 w-2 rounded-full ${dot}`} />
        <span className="text-xs text-ink-300" role="status">
          {conn.state === "connected" ? "Connected" : conn.state === "connecting" ? "Connecting…" : conn.reason}
        </span>
        {note && <span className="text-xs text-accent">{note}</span>}
        <div className="ml-auto flex items-center gap-1">
          {conn.state === "closed" && (
            <button className={btn} onClick={() => setAttempt((a) => a + 1)}><RotateCw className="h-3.5 w-3.5" />Reconnect</button>
          )}
          <button className={btn} onClick={() => term.current?.clear()} title="Clear the screen"><Eraser className="h-3.5 w-3.5" />Clear</button>
          <button className={btn} onClick={copy} title="Copy selection"><ClipboardCopy className="h-3.5 w-3.5" />Copy</button>
          <button className={btn} onClick={paste} disabled={conn.state !== "connected"} title="Paste"><ClipboardPaste className="h-3.5 w-3.5" />Paste</button>
          <button className={btn} onClick={onClose} title="Delete this sandbox"><X className="h-3.5 w-3.5" />End session</button>
        </div>
      </div>
      <div ref={host} className="min-h-0 flex-1 bg-[#0b0f17] p-2" />
    </div>
  );
}
