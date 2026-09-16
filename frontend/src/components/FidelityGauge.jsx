import { RadialBarChart, RadialBar, PolarAngleAxis, ResponsiveContainer } from "recharts";

export default function FidelityGauge({ score }) {
  const pct = Math.round(Math.max(0, Math.min(1, Number.isFinite(score) ? score : 0)) * 100);
  const color = pct >= 63 ? "#22c55e" : pct >= 50 ? "#f59e0b" : "#ef4444";

  const data = [
    { value: pct,  fill: color    },
  ];

  return (
    <div className="bg-[#0d1530] border border-white/10 rounded-xl p-5 flex flex-col items-center">
      <h3 className="text-sm font-semibold text-slate-300 mb-2">Fidelity Score</h3>
      <div className="relative w-40 h-40">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%" cy="50%"
            innerRadius="70%" outerRadius="100%"
            startAngle={180} endAngle={0}
            data={data}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar dataKey="value" cornerRadius={4} background={{ fill: "#1e293b" }} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center mt-6">
          <span className="text-3xl font-bold" style={{ color }}>{pct}%</span>
          <span className="text-xs text-slate-400">fidelity</span>
        </div>
      </div>
      <div className="mt-3 text-xs text-slate-400 text-center">
        Target: &gt;62.6% (beat ReflectRepro)
      </div>
      <div className="mt-1 flex gap-3 text-xs">
        <span className="text-red-400">▬ &lt;50%</span>
        <span className="text-amber-400">▬ 50–62%</span>
        <span className="text-green-400">▬ &gt;62%</span>
      </div>
    </div>
  );
}