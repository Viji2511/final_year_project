import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Dashboard from "./pages/Dashboard";
import RunPipeline from "./pages/RunPipeline";
import Results from "./pages/Results";

export default function App() {
  return (
    <div className="min-h-screen bg-[#0a0f1e]">
      <Navbar />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <Routes>
          <Route path="/"        element={<Dashboard />} />
          <Route path="/run"     element={<RunPipeline />} />
          <Route path="/results" element={<Results />} />
        </Routes>
      </main>
    </div>
  );
}