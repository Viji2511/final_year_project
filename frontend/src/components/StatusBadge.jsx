export default function StatusBadge({ status }) {
  const map = {
    running:  { label: "Running",  cls: "bg-amber-500/20  text-amber-400  border-amber-500/30" },
    complete: { label: "Complete", cls: "bg-green-500/20  text-green-400  border-green-500/30" },
    error:    { label: "Error",    cls: "bg-red-500/20    text-red-400    border-red-500/30"   },
    "not found": { label: "Not Found", cls: "bg-slate-500/20 text-slate-400 border-slate-500/30" },
  };
  const { label, cls } = map[status] || map["not found"];
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${cls}`}>
      {label}
    </span>
  );
}