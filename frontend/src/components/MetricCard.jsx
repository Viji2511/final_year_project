export default function MetricCard({ label, value, unit = "", highlight = false }) {
  return (
    <div className={`rounded-xl border p-4 ${
      highlight
        ? "bg-brand/10 border-brand/30"
        : "bg-[#0d1530] border-white/10"
    }`}>
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${highlight ? "text-brand" : "text-white"}`}>
        {value}
        {unit && <span className="text-sm font-normal text-slate-400 ml-1">{unit}</span>}
      </p>
    </div>
  );
}