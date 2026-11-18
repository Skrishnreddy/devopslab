import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity, BookOpen, Boxes, Container, FolderKanban, Gauge, Hammer, LifeBuoy, Server, Settings,
  Settings2, Shield, SquareTerminal, Workflow, Wrench, type LucideIcon,
} from "lucide-react";
import { api } from "../api";
import { useApi } from "../lib/useApi";

interface NavItem { to: string; label: string; icon: LucideIcon; planned?: boolean }

const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", icon: Gauge },
  { to: "/learn", label: "Learn", icon: BookOpen },
  { to: "/topics/linux", label: "Linux", icon: Server, planned: true },
  { to: "/topics/docker", label: "Docker", icon: Container, planned: true },
  { to: "/kubernetes", label: "Kubernetes", icon: Boxes },
  { to: "/topics/terraform", label: "Terraform", icon: Hammer, planned: true },
  { to: "/topics/jenkins", label: "Jenkins", icon: Workflow, planned: true },
  { to: "/topics/ansible", label: "Ansible", icon: Settings2, planned: true },
  { to: "/topics/prometheus", label: "Monitoring", icon: Activity, planned: true },
  { to: "/topics/devsecops", label: "DevSecOps", icon: Shield, planned: true },
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/troubleshooting", label: "Troubleshooting", icon: LifeBuoy },
  { to: "/terminal", label: "Terminal", icon: SquareTerminal, planned: true },
  { to: "/settings", label: "Settings", icon: Settings },
];

const ENGINEER = ["/projects", "/troubleshooting", "/kubernetes", "/terminal"];

function ModeSwitch() {
  const { pathname } = useLocation();
  const nav = useNavigate();
  const engineer = ENGINEER.some((p) => pathname.startsWith(p));
  const btn = (active: boolean) =>
    `flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition ${active ? "bg-accent font-semibold text-ink-950" : "text-ink-400 hover:text-white"}`;
  return (
    <div className="flex rounded-lg bg-ink-800 p-1" role="tablist" aria-label="Mode">
      <button className={btn(!engineer)} onClick={() => nav("/learn")} role="tab" aria-selected={!engineer}>
        <BookOpen className="h-4 w-4" />Learn
      </button>
      <button className={btn(engineer)} onClick={() => nav("/projects")} role="tab" aria-selected={engineer}>
        <Wrench className="h-4 w-4" />Engineer
      </button>
    </div>
  );
}

function ClusterIndicator() {
  const { data: c, error } = useApi(api.cluster, 15_000);
  const up = c?.connected;
  const label = error ? "API error" : !c ? "checking…" : up ? c.context.replace(/^kind-/, "") : "offline";
  return (
    <div className="flex items-center gap-2 text-sm" title={c?.reason ?? error?.message}>
      <span className={`h-2.5 w-2.5 rounded-full ${up ? "bg-ok" : c || error ? "bg-bad" : "bg-ink-700"}`} />
      <span className="hidden text-ink-400 sm:inline">Cluster:</span>
      <span className="font-mono text-white">{label}</span>
    </div>
  );
}

export default function Layout() {
  return (
    <div className="flex h-full">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-ink-700 bg-ink-900 md:flex">
        <div className="px-5 pb-3 pt-4">
          <div className="text-lg font-bold text-white">DevOps<span className="text-accent">Lab</span></div>
          <div className="text-[11px] text-ink-400">Learn. Build. Break. Troubleshoot. Master.</div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-4" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon, planned }) => (
            <NavLink key={to} to={to} end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm ${isActive ? "bg-ink-800 text-white" : "text-ink-400 hover:bg-ink-800/60 hover:text-ink-200"}`}>
              <Icon className="h-4 w-4" />
              <span className="flex-1">{label}</span>
              {planned && <span className="text-[10px] uppercase tracking-wide text-ink-700">planned</span>}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-ink-700 px-4 py-3 md:px-6">
          <ModeSwitch />
          <ClusterIndicator />
        </header>
        <main className="flex-1 overflow-y-auto p-4 md:p-6"><Outlet /></main>
      </div>
    </div>
  );
}
