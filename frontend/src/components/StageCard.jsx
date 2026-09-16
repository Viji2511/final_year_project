import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";

const STAGE_META = [
  { id: 1, label: "Text Extraction",      sub: "MinerU / PyMuPDF",         color: "text-blue-400"   },
  { id: 2, label: "Multimodal Extraction",sub: "Figures · Equations · Tables", color: "text-purple-400", novel: true },
  { id: 3, label: "Context Fusion",       sub: "UES Assembly",              color: "text-blue-400"   },
  { id: 4, label: "Code Generation",      sub: "Groq code generation",        color: "text-blue-400"   },
  { id: 5, label: "Execute & Validate",   sub: "Docker sandbox",            color: "text-blue-400"   },
];

export default function StageCard({ activeStage, status, mode = "generate_only" }) {
  return (
    <div className="bg-[#0d1530] border border-white/10 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-slate-300 mb-4">Pipeline Stages</h3>
      <div className="space-y-3">
        {STAGE_META.map((s) => {
          const skipped = s.id === 5 && mode === "generate_only";
          const done = !skipped && (activeStage > s.id || status === "complete");
          const active  = !skipped && activeStage === s.id && status === "running";
          const waiting = activeStage < s.id && status === "running";
          const errored = status === "error" && activeStage === s.id;

          return (
            <div key={s.id} className="flex items-center gap-3">
              <div className="flex-shrink-0">
                {errored ? (
                  <XCircle size={18} className="text-red-400" />
                ) : done ? (
                  <CheckCircle2 size={18} className="text-green-400" />
                ) : active ? (
                  <Loader2 size={18} className="text-brand animate-spin" />
                ) : (
                  <Circle size={18} className="text-slate-600" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-medium ${done || active ? "text-white" : "text-slate-500"}`}>
                    Stage {s.id} — {s.label}
                  </span>
                  {s.novel && (
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple/20 text-purple border border-purple/30">
                      NOVEL
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500">{skipped ? "Skipped in generate-only mode" : s.sub}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}