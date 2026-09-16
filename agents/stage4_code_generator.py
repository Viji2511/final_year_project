import json
import os
import re
import tempfile
from pathlib import Path
from validation import validate_paper_id
from loguru import logger
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL, OUTPUT_DIR
from schemas.ues_schema import UES



CODE_SYSTEM_PROMPT = """
You are an expert ML engineer. Generate complete, executable Python code to reproduce
a machine learning experiment from a paper specification. Rules:
- Implement mathematics exactly as specified in the SymPy/LaTeX expressions provided
- Generate modular code: data_loader.py, model.py, train.py, evaluate.py, requirements.txt, run.sh
- Use only standard/pip-installable libraries
- Print final evaluation metrics to stdout as metric_name: numeric_value
- run.sh must install no dependencies and run training followed by evaluation; exit on errors (set -e)
- Add clear comments referencing the paper specification
- Return a JSON dict: {"filename": "code content", ...}
- Do NOT hallucinate datasets or model details not in the specification
"""

def generate_code(ues: UES) -> str:
    """
    Stage 4: Generate executable Python repository from UES.
    Returns path to generated repository directory.
    """
    logger.info(f"Stage 4: Generating code for paper {ues.paper_id}")

    validate_paper_id(ues.paper_id)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    repo_dir = tempfile.mkdtemp(prefix=f"{ues.paper_id}_attempt_{ues.retry_count + 1}_", dir=OUTPUT_DIR)

    ues_summary = _build_ues_summary(ues)
    error_context = f"\nPrevious error to fix:\n{ues.error_report}" if ues.error_report else ""

    prompt = f"""
{error_context}

Generate a complete Python repository for this ML paper experiment:

{ues_summary}

Return ONLY a JSON object mapping filename to file content:
{{
  "data_loader.py": "...",
  "model.py": "...",
  "train.py": "...",
  "evaluate.py": "...",
  "requirements.txt": "...",
  "run.sh": "#!/bin/bash\\npython train.py"
}}
"""

    try:
        response = Groq(api_key=GROQ_API_KEY).chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": CODE_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        files = json.loads(raw)

        if not isinstance(files, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()):
            raise ValueError("Generated repository must map filenames to text")
        if not {"requirements.txt", "run.sh"}.issubset(files):
            raise ValueError("Generated repository requires requirements.txt and run.sh")
        root = Path(repo_dir).resolve()
        targets = []
        for filename, content in files.items():
            target = (root / filename).resolve()
            if not target.is_relative_to(root) or target == root or target.name.lower() == "dockerfile":
                raise ValueError(f"Unsafe generated filename: {filename}")
            targets.append((target, content))
        for target, content in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        logger.info(f"Stage 4 complete. Repository at {repo_dir}")
        return repo_dir

    except Exception as e:
        logger.error(f"Stage 4 code generation failed: {e}")
        raise


def _build_ues_summary(ues: UES) -> str:
    """Serialise UES to a concise string for the prompt."""
    loss = ues.loss_function.latex_str if ues.loss_function else "not specified"
    metrics = [e.latex_str for e in ues.evaluation_metrics[:3]]
    baselines = [(b.model_name, b.metric, b.value) for b in ues.baseline_comparisons[:5]]
    fig_info = [
        f"{f.figure_id}({f.chart_type}): x={f.x_axis.label if f.x_axis else '?'}, "
        f"y={f.y_axis.label if f.y_axis else '?'}, series={[s.name for s in f.series]}"
        for f in ues.figures[:3]
    ]

    return f"""
Title: {ues.title}
Task: {ues.task}
Dataset: {ues.dataset}
Model Architecture: {ues.model_architecture}
Hyperparameters: {json.dumps(ues.hyperparameters, indent=2)}
Loss Function (LaTeX): {loss}
Evaluation Metrics (LaTeX): {metrics}
Training Procedure: {(ues.training_procedure or '')[:500]}
Algorithms: {ues.algorithms[:2]}
Figures: {fig_info}
Target Results (baselines): {baselines}
"""