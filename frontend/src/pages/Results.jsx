import { useEffect, useState } from "react";
import { BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { listResults } from "../api/mrep";
import StatusBadge from "../components/StatusBadge";
import MetricCard from "../components/MetricCard";
import FidelityGauge from "../components/FidelityGauge";

const BASELINES = [
  { name: "PaperCoder",    score: 51.14 },
  { name: "AutoReproduce", score: 49.6  },
  { name: "ReflectRepro",  score: 62.6  },
];

export default function Results() {
  const [results,  setResults]  = useState({});
  const [selected, setSelected] = useState(null);

  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    listResults().then((data) => { setResults(data); setLoadError(""); }).catch(() => setLoadError("Unable to load results. Check that the API server is running."));
    const id = setInterval(() => {
      listResults().then((data) => { setResults(data); setLoadError(""); }).catch(() => setLoadError("Unable to load results. Check that the API server is running."));
    }, 5000);
    return () => clearInterval(id);
  }, []);

  const entries   = Object.entries(results);
  const completed = entries.filter(([, r]) => r.status === "complete" && r.fidelity_score != null);

  // Build chart data — baselines + MRep results
  const chartData = [
    ...BASELINES.map((b) => ({
      name:  b.name,
      score: b.score,
      fill:  "#475569",
    })),
    ...completed.map(([id, r]) => ({
      name:  id.length > 12 ? id.slice(0, 12) + "…" : id,
      score: Math.round((r.fidelity_score || 0) * 100),
      fill:  (r.fidelity_score || 0) >= 0.626 ? "#22c55e" : "#2a78d6",
    })),
  ];

  const selectedResult = selected ? results[selected] : null;

  return (
    <div className="space-y-8">
      {loadError && <p role="alert" className="text-sm text-red-400">{loadError}</p>}
      <div>
        <h1 className="text-2xl font-bold text-white">Results</h1>
        <p className="text-slate-400 text-sm mt-1">
          MRep fidelity scores compared against text-only baselines
        </p>
      </div>

      {/* Comparison chart */}
      <div className="bg-[#0d1530] border border-white/10 rounded-xl p-6">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">
          Fidelity Score Comparison (Code-Dev)
        </h2>
        {completed.length === 0 ? (
          <p className="text-slate-500 text-sm text-center py-8">
            No validated results yet. Generate-only runs have no fidelity score.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} barSize={36}>
              <XAxis
                dataKey="name"
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                axisLine={false} tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                axisLine={false} tickLine={false}
                unit="%"
              />
              <Tooltip
                contentStyle={{
                  background: "#0d1530", border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 8, color: "#f1f5f9", fontSize: 12,
                }}
                formatter={(v) => [`${v}%`, "Fidelity"]}
              />
              <ReferenceLine
                y={62.6} stroke="#f59e0b" strokeDasharray="4 3"
                label={{ value: "ReflectRepro 62.6%", fill: "#f59e0b", fontSize: 10, position: "insideTopRight" }}
              />
              <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Results list */}
      <div className="grid md:grid-cols-3 gap-6">
        <div className="md:col-span-1 space-y-2">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Papers</h2>
          {entries.length === 0 ? (
            <p className="text-slate-500 text-sm">No papers processed.</p>
          ) : (
            entries.map(([paperId, r]) => (
              <button
                key={paperId}
                onClick={() => setSelected(paperId)}
                className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                  selected === paperId
                    ? "bg-brand/10 border-brand/40"
                    : "bg-[#0d1530] border-white/10 hover:border-white/20"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-white truncate">{paperId}</span>
                  <StatusBadge status={r.status} />
                </div>
                {r.fidelity_score != null && (
                  <span className={`text-xs font-semibold ${
                    r.fidelity_score >= 0.626 ? "text-green-400" :
                    r.fidelity_score >= 0.5   ? "text-amber-400" : "text-red-400"
                  }`}>
                    {Math.round(r.fidelity_score * 100)}% fidelity
                  </span>
                )}
              </button>
            ))
          )}
        </div>

        {/* Detail panel */}
        <div className="md:col-span-2">
          {selectedResult ? (
            <div className="space-y-4">
              <h2 className="text-sm font-semibold text-slate-300">{selected}</h2>
              <div className="grid grid-cols-2 gap-3">
                <MetricCard label="Fidelity Score"
                  value={selectedResult.fidelity_score == null ? "Not evaluated" : `${Math.round(selectedResult.fidelity_score * 100)}%`}
                  highlight
                />
                <MetricCard label="Attempts"        value={selectedResult.attempts ?? "—"} />
                <MetricCard label="Figures Extracted"    value={selectedResult.figures_extracted   ?? "—"} />
                <MetricCard label="Equations Extracted"  value={selectedResult.equations_extracted ?? "—"} />
                <MetricCard label="Tables Extracted"     value={selectedResult.tables_extracted    ?? "—"} />
                <MetricCard label="Status"           value={selectedResult.status} />
              </div>
              {selectedResult.error && <p className="text-red-400 text-sm">{selectedResult.error}</p>}
              {selectedResult.mode === "generate_only" && <p className="text-sm text-slate-300">Code generated. Execution and validation skipped.</p>}
              {selectedResult.repo_dir && <p className="text-xs text-slate-300 break-all">Saved on backend: {selectedResult.repo_dir}</p>}
              {selectedResult.fidelity_score != null && <FidelityGauge score={selectedResult.fidelity_score ?? 0} />}
            </div>
          ) : (
            <div className="flex items-center justify-center h-48 text-slate-500 text-sm">
              Select a paper to see details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}