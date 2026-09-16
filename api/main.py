import os
import shutil
from threading import Lock
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from config import PAPERS_DIR, PIPELINE_MODE, validate_api_keys
from pipeline import run_pipeline
from validation import validate_paper_id

app = FastAPI(title="MRep API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
results_store = {}
_store_lock = Lock()

@app.get("/")
def root():
    return {"status": "MRep API running", "mode": PIPELINE_MODE}

@app.post("/run", status_code=202)
def run_paper(background_tasks: BackgroundTasks, paper_id: str, file: UploadFile = File(...)):
    try:
        validate_paper_id(paper_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not file.filename or not file.filename.lower().endswith(".pdf") or file.file.read(5) != b"%PDF-":
        raise HTTPException(400, "Upload a valid PDF file.")
    file.file.seek(0)
    try:
        validate_api_keys()
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc
    with _store_lock:
        if results_store.get(paper_id, {}).get("status") == "running":
            raise HTTPException(409, "This paper is already running.")
        results_store[paper_id] = {"status": "running", "stage": 0, "mode": PIPELINE_MODE}
    pdf_path = os.path.join(PAPERS_DIR, f"{paper_id}.pdf")
    try:
        with open(pdf_path, "wb") as destination:
            shutil.copyfileobj(file.file, destination)
    except Exception:
        results_store[paper_id] = {"status": "error", "error": "Could not save uploaded PDF."}
        raise
    finally:
        file.file.close()
    background_tasks.add_task(_run_and_store, pdf_path, paper_id)
    return {"paper_id": paper_id, "status": "started", "mode": PIPELINE_MODE}

@app.get("/result/{paper_id}")
def get_result(paper_id: str):
    if paper_id not in results_store:
        raise HTTPException(404, "Paper not found")
    return results_store[paper_id]

@app.get("/results")
def list_results():
    with _store_lock:
        return dict(results_store)

def _run_and_store(pdf_path: str, paper_id: str):
    def update_stage(stage):
        results_store[paper_id] = {"status": "running", "stage": stage, "mode": PIPELINE_MODE}
    try:
        result = run_pipeline(pdf_path, paper_id, on_stage=update_stage)
        results_store[paper_id] = {**result, "status": "complete", "stage": 6}
    except Exception as exc:
        error_details = str(exc)
        if "groq" in error_details.lower():
            if "generation_truncated" in error_details.lower():
                parts = error_details.split("|")
                filename = parts[1] if len(parts) > 1 else "unknown"
                error_details = {
                    "stage": "code_generation",
                    "provider": "groq",
                    "error_code": "GENERATION_TRUNCATED",
                    "filename": filename,
                    "message": "Generation reached the configured output-token limit.",
                    "recoverable": False
                }
            elif "does not exist" in error_details.lower() or "not available" in error_details.lower() or "model_not_found" in error_details.lower():
                from config import GROQ_MODEL
                error_details = {
                    "stage": "code_generation",
                    "provider": "groq",
                    "error_code": "MODEL_NOT_FOUND",
                    "message": "The configured Groq model is unavailable.",
                    "configured_model": GROQ_MODEL,
                    "recoverable": True
                }
            elif "api key" in error_details.lower():
                error_details = {
                    "stage": "code_generation",
                    "provider": "groq",
                    "error_code": "INVALID_API_KEY",
                    "message": "The provided Groq API key is invalid or missing.",
                    "recoverable": True
                }
            else:
                error_details = {
                    "stage": "code_generation",
                    "provider": "groq",
                    "error_code": "CODE_GENERATION_FAILED",
                    "message": "An error occurred during code generation with Groq.",
                    "recoverable": False
                }
        results_store[paper_id] = {"status": "error", "stage": results_store[paper_id].get("stage", 0), "error": error_details}
