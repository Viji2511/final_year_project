import json
import re
from loguru import logger
from typing import Dict, Any
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL
from schemas.ues_schema import UES, BaselineComparison
from schemas.equation_schema import EquationData




def fuse_context(
    paper_id: str,
    text_context: Dict[str, Any],
    multimodal: Dict[str, Any],
) -> UES:
    """
    Stage 3: Fuse text + multimodal into Unified Experimental Specification.
    """
    logger.info(f"Stage 3: Fusing context for paper {paper_id}")

    figures   = multimodal.get("figures", [])
    equations = multimodal.get("equations", [])
    tables    = multimodal.get("tables", [])

    # Identify loss function and evaluation metrics from equations
    loss_fn, eval_metrics = _classify_equations(equations, text_context)

    # Identify result tables
    result_tables = [t for t in tables if t.is_result_table]

    # Extract baseline comparisons from result tables
    baselines = _extract_baselines(result_tables)

    # Use LLM to resolve cross-modal ambiguities
    resolved = _resolve_ambiguities(text_context, figures, equations)

    ues = UES(
        paper_id=paper_id,
        arxiv_id=text_context.get("arxiv_id"),
        title=text_context.get("title"),
        task=resolved.get("task") or text_context.get("task"),
        dataset=resolved.get("dataset") or text_context.get("dataset"),
        model_architecture=text_context.get("model_architecture"),
        hyperparameters=text_context.get("hyperparameters", {}),
        loss_function=loss_fn,
        evaluation_metrics=eval_metrics,
        figures=figures,
        result_tables=result_tables,
        training_procedure=text_context.get("methodology"),
        baseline_comparisons=baselines,
        methodology_text=text_context.get("methodology"),
        algorithms=text_context.get("algorithms", []),
    )

    logger.info("Stage 3 complete. UES built.")
    return ues


def _classify_equations(equations, text_context):
    """Separate loss function from evaluation metric equations."""
    loss_keywords = ["loss", "l(", "l =", "objective", "criterion", "cross_entropy"]
    metric_keywords = ["accuracy", "f1", "precision", "recall", "bleu", "rouge"]

    loss_fn = None
    eval_metrics = []

    methodology = text_context.get("methodology", "").lower()

    for eq in equations:
        latex_lower = eq.latex_str.lower()
        is_loss = any(kw in latex_lower for kw in loss_keywords)
        is_metric = any(kw in latex_lower for kw in metric_keywords)

        if is_loss and not loss_fn:
            eq.description = "loss_function"
            loss_fn = eq
        elif is_metric:
            eq.description = "evaluation_metric"
            eval_metrics.append(eq)

    return loss_fn, eval_metrics


def _extract_baselines(result_tables):
    """Extract baseline model comparisons from result tables."""
    baselines = []
    for table in result_tables:
        if not table.columns or not table.values:
            continue
        col_names = [c.name for c in table.columns]
        for row_idx, row_label in enumerate(table.row_labels):
            if row_idx < len(table.values):
                for col_idx, col in enumerate(table.columns):
                    if col.dtype == "float" and col_idx < len(table.values[row_idx]):
                        val = table.values[row_idx][col_idx]
                        if isinstance(val, (int, float)):
                            baselines.append(BaselineComparison(
                                model_name=row_label,
                                metric=col.name,
                                value=float(val),
                            ))
    return baselines


def _resolve_ambiguities(text_context, figures, equations):
    """Use LLM to resolve cross-modal ambiguities."""
    fig_summary = [
        f"{f.figure_id}: {f.chart_type}, x={f.x_axis.label if f.x_axis else 'N/A'}, "
        f"y={f.y_axis.label if f.y_axis else 'N/A'}"
        for f in figures[:5]
    ]
    eq_summary = [e.latex_str[:80] for e in equations[:5]]

    prompt = f"""
Given this paper context, resolve any ambiguities and return ONLY JSON:

Task from text: {text_context.get('task')}
Dataset from text: {text_context.get('dataset')}
Figures found: {fig_summary}
Equations found: {eq_summary}

Return ONLY:
{{"task": "corrected task description", "dataset": "corrected dataset name"}}
"""
    try:
        response = Groq(api_key=GROQ_API_KEY).chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Ambiguity resolution failed: {e}")
        return {}