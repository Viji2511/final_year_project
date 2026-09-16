import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Play, FileText, FlaskConical, TrendingUp } from "lucide-react";
import { listResults } from "../api/mrep";
import StatusBadge from "../components/StatusBadge";
import MetricCard from "../components/MetricCard";

export default function Dashboard() {
  const [results, setResults] = useState({});

  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    listResults().then((data) => { setResults(data); setLoadError(""); }).catch(() => setLoadError("Unable to load results. Check that the API server is running."));
    const id = setInterval(() => {
      listResults().then((data) => { setResults(data); setLoadError(""); }).catch(() => setLoadError("Unable to load results. Check that the API server is running."));
    }, 5000);
    return () => clearInterval(id);
  }, []);

  const entries  = Object.entries(results);
  const total    = entries.length;
  const complete = entries.filter(([, r]) => r.status === "complete").length;
  const scored = entries.filter(([, r]) => r.status === "complete" && r.fidelity_score != null);
  const avgScore = scored.length > 0
    ? scored
        .reduce((s, [, r]) => s + (r.fidelity_score || 0), 0) / scored.length
    : 0;

  return (
    <div className="space-y-8">
      {loadError && <p role="alert" className="text-sm text-red-400">{loadError}</p>}
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">MRep Dashboard</h1>
          <p className="text-slate-400 text-sm mt-1">
            Multimodal Experiment Reproduction Pipeline
          </p>
        </div>
        <Link
          to="/run"
          className="flex items-center gap-2 px-4 py-2 bg-brand hover:bg-brand/90 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Play size={14} />
          Run Pipeline
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Papers Processed" value={total} />
        <MetricCard label="Completed"         value={complete} />
        <MetricCard
          label="Avg Fidelity"
          value={scored.length ? `${Math.round(avgScore * 100)}%` : "Not evaluated"}
          highlight
        />
        <MetricCard label="Target Baseline" value="62.6%" unit="ReflectRepro" />
      </div>

      {/* Papers table */}
      <div className="bg-[#0d1530] border border-white/10 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-white/10 flex items-center gap-2">
          <FileText size={15} className="text-brand" />
          <h2 className="text-sm font-semibold text-white">Papers</h2>
        </div>

        {entries.length === 0 ? (
          <div className="px-5 py-12 text-center text-slate-500">
            <FlaskConical size={32} className="mx-auto mb-3 opacity-40" />
            <p className="text-sm">No papers processed yet.</p>
            <Link to="/run" className="text-brand text-sm hover:underline mt-1 inline-block">
              Run your first paper →
            </Link>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-400 border-b border-white/5">
                <th className="text-left px-5 py-3 font-medium">Paper ID</th>
                <th className="text-left px-5 py-3 font-medium">Status</th>
                <th className="text-left px-5 py-3 font-medium">Fidelity</th>
                <th className="text-left px-5 py-3 font-medium">Figures</th>
                <th className="text-left px-5 py-3 font-medium">Equations</th>
                <th className="text-left px-5 py-3 font-medium">Attempts</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(([paperId, r]) => (
                <tr
                  key={paperId}
                  className="border-b border-white/5 hover:bg-white/3 transition-colors"
                >
                  <td className="px-5 py-3 font-mono text-xs text-slate-300">{paperId}</td>
                  <td className="px-5 py-3"><StatusBadge status={r.status} /></td>
                  <td className="px-5 py-3">
                    {r.fidelity_score != null ? (
                      <span className={`font-semibold ${
                        r.fidelity_score >= 0.626 ? "text-green-400" :
                        r.fidelity_score >= 0.5   ? "text-amber-400" : "text-red-400"
                      }`}>
                        {Math.round(r.fidelity_score * 100)}%
                      </span>
                    ) : "—"}
                  </td>
                  <td className="px-5 py-3 text-slate-400">{r.figures_extracted ?? "—"}</td>
                  <td className="px-5 py-3 text-slate-400">{r.equations_extracted ?? "—"}</td>
                  <td className="px-5 py-3 text-slate-400">{r.attempts ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}