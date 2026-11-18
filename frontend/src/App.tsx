import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./lib/auth";
import AITeacher from "./pages/AITeacher";
import Dashboard from "./pages/Dashboard";
import Kubernetes from "./pages/Kubernetes";
import Learn from "./pages/Learn";
import Login from "./pages/Login";
import Projects from "./pages/Projects";
import Settings from "./pages/Settings";
import Topic from "./pages/Topic";
import Troubleshooting from "./pages/Troubleshooting";

// xterm.js is large; load it only when the Terminal page opens.
const Terminal = lazy(() => import("./pages/Terminal"));

function RequireAuth() {
  const { me, checking } = useAuth();
  if (checking) return <div className="p-6 text-ink-400">Loading…</div>;
  return me ? <Outlet /> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="learn" element={<Learn />} />
          <Route path="kubernetes" element={<Kubernetes />} />
          <Route path="topics/:id" element={<Topic />} />
          <Route path="projects" element={<Projects />} />
          <Route path="troubleshooting" element={<Troubleshooting />} />
          <Route path="terminal" element={<Suspense fallback={<div className="p-6 text-ink-400">Loading…</div>}><Terminal /></Suspense>} />
          <Route path="ai-teacher" element={<AITeacher />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
