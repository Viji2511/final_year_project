import json
import os
import re
import tempfile
import py_compile
from pathlib import Path
from loguru import logger
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL, OUTPUT_DIR, GROQ_PLANNER_MAX_TOKENS, GROQ_CODEGEN_MAX_TOKENS
from schemas.ues_schema import UES
from validation import validate_paper_id

class GenerationTruncatedError(Exception):
    def __init__(self, filename, completion_tokens, limit):
        self.filename = filename
        self.completion_tokens = completion_tokens
        self.limit = limit
        super().__init__(f"GENERATION_TRUNCATED: {filename} reached limit {limit}")

def build_codegen_context(ues: UES) -> str:
    """Build a reduced context from UES for the planner and cross-file consistency."""
    loss = ues.loss_function.latex_str if ues.loss_function else "not specified"
    metrics = [e.latex_str for e in ues.evaluation_metrics[:3]]
    baselines = [(b.model_name, b.metric, b.value) for b in ues.baseline_comparisons[:5]]
    
    return f"""
Task: {ues.task}
Dataset: {ues.dataset}
Architecture: {ues.model_architecture}
Hyperparameters: {json.dumps(ues.hyperparameters)}
Loss: {loss}
Metrics: {metrics}
Baselines: {baselines}
"""

def plan_repository(ues: UES, repo_dir: str) -> dict:
    """Generate the repository plan."""
    logger.info("Stage 4: Planning repository structure.")
    context = build_codegen_context(ues)
    
    prompt = f"""
Based on the following experiment:
{context}

Create a repository plan outlining the required files for this ML experiment.
You MUST include at least: data_loader.py, model.py, train.py, evaluate.py, requirements.txt, run.sh.

Return ONLY a JSON object with this structure:
{{
  "files": [
    {{"path": "data_loader.py", "purpose": "Loads the dataset...", "interfaces": "get_dataloaders(config)"}},
    {{"path": "model.py", "purpose": "Defines the model architecture...", "interfaces": "build_model(config)"}}
  ]
}}
"""
    
    response = Groq(api_key=GROQ_API_KEY).chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You are a repository planner."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=GROQ_PLANNER_MAX_TOKENS,
    )
    
    if response.choices[0].finish_reason == "length":
        raise GenerationTruncatedError("repository_plan.json", response.usage.completion_tokens, GROQ_PLANNER_MAX_TOKENS)
        
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)

def generate_file(ues: UES, plan: dict, file_info: dict, repo_dir: str, attempt: int = 1, error_feedback: str = "") -> str:
    """Generate a single file."""
    filename = file_info["path"]
    logger.info(f"Stage 4: Generating {filename} (Attempt {attempt})")
    
    context = build_codegen_context(ues)
    plan_summary = json.dumps(plan, indent=2)
    
    prompt = f"""
Experiment Context:
{context}

Repository Plan:
{plan_summary}

Your task is to generate the complete, executable content for the file: {filename}
Purpose: {file_info.get("purpose", "")}
Interfaces to expose/use: {file_info.get("interfaces", "")}

{error_feedback}

Return ONLY the raw file content. Do NOT wrap it in markdown formatting like ```python. Do NOT include any explanations.
"""
    
    response = Groq(api_key=GROQ_API_KEY).chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You are an expert ML engineer generating a single file for a repository."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=GROQ_CODEGEN_MAX_TOKENS,
    )
    
    if response.choices[0].finish_reason == "length":
        raise GenerationTruncatedError(filename, response.usage.completion_tokens, GROQ_CODEGEN_MAX_TOKENS)
        
    content = response.choices[0].message.content.strip()
    content = re.sub(r"^```python\s*|^```[a-z]*\s*|```\s*$", "", content, flags=re.MULTILINE).strip()
    return content

def validate_generated_file(path: str, content: str) -> str:
    """Validate the generated file. Returns an error string if invalid, empty string if valid."""
    if not content.strip():
        return "File is empty."
    
    if path.endswith(".py"):
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as e:
            return f"SyntaxError: {e.exc_value}"
            
    if path == "run.sh" and "python" not in content:
        return "run.sh does not contain a python command to execute."
        
    return ""

def generate_code(ues: UES) -> str:
    """
    Stage 4: Generate executable Python repository from UES.
    Returns path to generated repository directory.
    """
    logger.info(f"Stage 4: Generating code for paper {ues.paper_id}")
    validate_paper_id(ues.paper_id)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    repo_dir = tempfile.mkdtemp(prefix=f"{ues.paper_id}_attempt_{ues.retry_count + 1}_", dir=OUTPUT_DIR)
    root = Path(repo_dir).resolve()
    
    try:
        plan = plan_repository(ues, repo_dir)
        
        manifest = {"paper_id": ues.paper_id, "files": {}}
        
        required_files = {"data_loader.py", "model.py", "train.py", "evaluate.py", "requirements.txt", "run.sh"}
        planned_files = {f["path"] for f in plan.get("files", [])}
        for req in required_files:
            if req not in planned_files:
                plan.setdefault("files", []).append({"path": req, "purpose": "Required repository file."})

        for file_info in plan.get("files", []):
            filename = file_info["path"]
            target = (root / filename).resolve()
            
            if not target.is_relative_to(root) or target == root or target.name.lower() == "dockerfile":
                logger.warning(f"Skipping unsafe filename: {filename}")
                continue
                
            success = False
            error_feedback = ""
            
            for attempt in range(1, 4):  # 3 attempts per file
                try:
                    content = generate_file(ues, plan, file_info, repo_dir, attempt, error_feedback)
                    
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")
                    
                    val_err = validate_generated_file(str(target), content)
                    if val_err:
                        error_feedback = f"Previous generation failed validation with error:\n{val_err}\nPlease fix it."
                        logger.warning(f"Validation failed for {filename}: {val_err}")
                        continue
                        
                    success = True
                    manifest["files"][filename] = "generated"
                    break
                except GenerationTruncatedError as e:
                    raise  # Bubble up truncation errors immediately
                except Exception as e:
                    error_feedback = f"Generation failed with error: {e}"
                    logger.warning(f"Generation attempt failed for {filename}: {e}")
            
            if not success:
                manifest["files"][filename] = "failed"
                raise ValueError(f"Failed to generate {filename} after 3 attempts.")
                
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        
        logger.info(f"Stage 4 complete. Repository at {repo_dir}")
        return repo_dir

    except GenerationTruncatedError as e:
        logger.error(str(e))
        raise ValueError(f"Groq API Error: GENERATION_TRUNCATED|{e.filename}|{e.limit}") from e
    except Exception as e:
        logger.error(f"Stage 4 code generation failed: {e}")
        raise ValueError(f"Groq API Error: {e}") from e