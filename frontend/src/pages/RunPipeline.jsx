import { useState, useRef, useEffect } from "react";
import { Upload, Play, FileText, CheckCircle2, AlertCircle } from "lucide-react";
import { uploadPaper, pollResult } from "../api/mrep";
import StageCard from "../components/StageCard";
import FidelityGauge from "../components/FidelityGauge";
import MetricCard from "../components/MetricCard";

export default function RunPipeline() {
  const [file,     setFile]     = useState(null);
  const [paperId,  setPaperId]  = useState("");
  const [status,   setStatus]   = useState("idle");  // idle | uploading | running | complete | error
  const [result,   setResult]   = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [mode, setMode] = useState("generate_only");
  const [stage,    setStage]    = useState(0);
  const inputRef = useRef();
  const stopPoll = useRef(null);

  useEffect(() => () => stopPoll.current?.(), []);

  const handleFile = (e) => {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      if (!paperId) {
        setPaperId(f.name.replace(/\.pdf$/i, "").replace(/[^a-zA-Z0-9_-]+/g, "_").replace(/^[^a-zA-Z0-9]+/, "").slice(0, 100).toLowerCase());
      }
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f?.type === "application/pdf") {
      setFile(f);
      if (!paperId) {
        setPaperId(f.name.replace(/\.pdf$/i, "").replace(/[^a-zA-Z0-9_-]+/g, "_").replace(/^[^a-zA-Z0-9]+/, "").slice(0, 100).toLowerCase());
      }
    }
  };

  const handleRun = async () => {
    if (!file || !paperId.trim()) return;
    stopPoll.current?.();
    setStatus("uploading");
    setResult(null);
    setErrorMsg("");
    setStage(1);

    try {
      const started = await uploadPaper(paperId.trim(), file);
      setMode(started.mode || "generate_only");
      setStatus("running");

      stopPoll.current = pollResult(paperId.trim(), (r) => {
        if (r.stage != null) setStage(r.stage);
        if (r.status === "complete") {
          setStage(6);
          setStatus("complete");
          setResult(r);
        } else if (r.status === "error") {
          setStatus("error");
          setErrorMsg(r.error || "Unknown error");
        }
      });
    } catch (e) {
      setStatus("error");
      const detail = e?.response?.data?.detail;
      setErrorMsg(typeof detail === "string" ? detail : e.message || "Upload failed");
    }
  };

  const handleReset = () => {
    stopPoll.current?.();
    setFile(null); setPaperId(""); setStatus("idle");
    setResult(null); setErrorMsg(""); setStage(0);
  };

  return (
    <div className="space-y-8 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-white">Run Pipeline</h1>
        <p className="text-slate-400 text-sm mt-1">
          Upload a paper PDF to extract its experiments and generate reproduction code.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Left — upload */}
        <div className="space-y-4">
          {/* Drop zone */}
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => inputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
              file
                ? "border-brand/60 bg-brand/5"
                : "border-white/10 hover:border-white/20 bg-white/2"
            }`}
          >
            <input
              ref={inputRef} type="file" accept=".pdf"
              className="hidden" onChange={handleFile}
            />
            {file ? (
              <div className="space-y-2">
                <FileText size={32} className="mx-auto text-brand" />
                <p className="text-sm font-medium text-white">{file.name}</p>
                <p className="text-xs text-slate-400">
                  {(file.size / 1024).toFixed(0)} KB
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <Upload size={32} className="mx-auto text-slate-500" />
                <p className="text-sm text-slate-400">
                  Drop a PDF here or click to browse
                </p>
              </div>
            )}
          </div>

          {/* Paper ID */}
          <div>
            <label className="text-xs font-medium text-slate-400 block mb-1.5">
              Paper ID
            </label>
            <input
              value={paperId}
              onChange={(e) => setPaperId(e.target.value)}
              placeholder="e.g. papercoder_2025"
              className="w-full bg-[#0d1530] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand"
            />
          </div>

          {/* Run button */}
          {status === "idle" || status === "error" ? (
            <button
              onClick={handleRun}
              disabled={!file || !paperId.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand hover:bg-brand/90 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors"
            >
              <Play size={15} />
              Run MRep Pipeline
            </button>
          ) : (
            <button
              onClick={handleReset}
              disabled={status === "uploading" || status === "running"}
              className="w-full px-4 py-2.5 border border-white/10 hover:bg-white/5 text-slate-300 text-sm font-medium rounded-lg transition-colors"
            >
              Reset
            </button>
          )}

          {/* Error */}
          {status === "error" && errorMsg && (
            <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
              <AlertCircle size={15} className="text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-red-300">{errorMsg}</p>
            </div>
          )}

          {/* Success summary */}
          {status === "complete" && result && (
            <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4 space-y-2">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={15} className="text-green-400" />
                <span className="text-sm font-semibold text-green-400">{result.mode === "generate_only" ? "Code generated - validation skipped" : result.passed ? "Reproduction passed" : "Reproduction did not pass validation"}</span>
              </div>
              {result.repo_dir && <p className="text-xs text-slate-300 break-all">Saved on backend: {result.repo_dir}</p>}
              <div className="grid grid-cols-2 gap-2 mt-2">
                <MetricCard label="Figures"   value={result.figures_extracted   ?? 0} />
                <MetricCard label="Equations" value={result.equations_extracted ?? 0} />
                <MetricCard label="Tables"    value={result.tables_extracted    ?? 0} />
                <MetricCard label="Attempts"  value={result.attempts            ?? 0} />
              </div>
            </div>
          )}
        </div>

        {/* Right — stages + gauge */}
        <div className="space-y-4">
          <StageCard
            mode={mode}
            activeStage={stage}
            status={status === "uploading" ? "running" : status}
          />
          {result?.fidelity_score != null && (
            <FidelityGauge score={result?.fidelity_score ?? 0} />
          )}
        </div>
      </div>
    </div>
  );
}