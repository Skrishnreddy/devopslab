import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity, BookOpen, Boxes, Container, FolderKanban, Gauge, Hammer, LifeBuoy, Server,
  Settings2, Shield, SquareTerminal, Workflow, Wrench,
} from "lucide-react";
import { api } from "../api";
import { useApi } from "../useApi";

const NAV = [
  { to: "/", label: "Dashboard", icon: Gauge },
  { to: "/learn", label: "Learn", icon: BookOpen },
  { to: "/engineer", label: "Projects", icon: FolderKanban },
  { to: "/kubernetes", label: "Kubernetes", icon: Boxes },
  { to: "/topic/docker", label: "Docker", icon: Container },
  { to: "/topic/linux", label: "Linux", icon: Server },
  { to: "/topic/terraform", label: "Terraform", icon: Hammer },
  { to: "/topic/jenkins", label: "Jenkins", icon: Workflow },
  { to: "/topic/ansible", label: "Ansible", icon: Settings2 },
  { to: "/topic/monitoring", label: "Monitoring", icon: Activity },
  { to: "/topic/devsecops", label: "DevSecOps", icon: Shield },
  { to: "/troubleshoot", label: "Troubleshoot", icon: LifeBuoy },
  { to: "/terminal", label: "Terminal", icon: SquareTerminal },
];

function ModeSwitch() {
  const { pathname } = useLocation();
  const nav = useNavigate();
  const engineer = pathname.startsWith("/engineer") || pathname.startsWith("/troubleshoot");
  const btn = (active: boolean) =>
    `px-3 py-1.5 rounded-md text-sm transition ${active ? "bg-accent text-ink-950 font-semibold" : "text-ink-400 hover:text-white"}`;
  return (
    <div className="flex rounded-lg bg-ink-800 p-1" role="tablist" aria-label="Mode">
      <button className={btn(!engineer)} onClick={() => nav("/learn")} role="tab" aria-selected={!engineer}>
        <BookOpen className="mr-1.5 inline h-4 w-4" />Learn
      </button>
      <button className={btn(engineer)} onClick={() => nav("/engineer")} role="tab" aria-selected={engineer}>
        <Wrench className="mr-1.5 inline h-4 w-4" />Engineer
      </button>
    </div>
  );
}

export default function Layout() {
  const { data: cluster } = useApi(api.cluster, 10_000);
  const up = cluster?.connected;
  return (
    <div className="flex h-full">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-ink-700 bg-ink-900 md:flex">
        <div className="px-5 py-4 text-lg font-bold text-white">
          DevOps<span className="text-accent">Lab</span>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-4">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm ${isActive ? "bg-ink-800 text-white" : "text-ink-400 hover:bg-ink-800/60 hover:text-ink-200"}`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-ink-700 px-6 py-3">
          <ModeSwitch />
          <div className="flex items-center gap-2 text-sm">
            <span className={`h-2.5 w-2.5 rounded-full ${up ? "bg-ok" : cluster ? "bg-bad" : "bg-ink-700"}`} />
            <span className="text-ink-400">Cluster:</span>
            <span className="font-mono text-white">{up ? cluster?.context?.replace(/^kind-/, "") : "offline"}</span>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
