import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Learn from "./pages/Learn";
import Engineer from "./pages/Engineer";
import Kubernetes from "./pages/Kubernetes";
import { Terminal, Topic } from "./pages/Placeholders";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="learn" element={<Learn />} />
        <Route path="engineer" element={<Engineer />} />
        <Route path="troubleshoot" element={<Engineer incidentsOnly />} />
        <Route path="kubernetes" element={<Kubernetes />} />
        <Route path="topic/:id" element={<Topic />} />
        <Route path="terminal" element={<Terminal />} />
        <Route path="*" element={<Topic />} />
      </Route>
    </Routes>
  );
}
