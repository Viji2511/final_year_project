import os
from loguru import logger
from config import MAX_RETRIES, PIPELINE_MODE, validate_api_keys
from validation import validate_paper_id


def run_pipeline(pdf_path: str, paper_id: str, on_stage=None) -> dict:
    """
    Generate code, optionally executing and validating it in full mode.
    Returns final result dict with fidelity score and status.
    """
    validate_paper_id(paper_id)
    validate_api_keys()
    from agents.stage1_text_extractor import extract_text_from_pdf
    from agents.stage2_multimodal.figure_parser import parse_figures
    from agents.stage2_multimodal.equation_extractor import extract_equations
    from agents.stage2_multimodal.table_structurizer import extract_tables
    from agents.stage2_multimodal.merge import merge_multimodal
    from agents.stage3_context_fusion import fuse_context
    from agents.stage4_code_generator import generate_code
    report_stage = on_stage or (lambda stage: None)

    logger.info(f"=== MRep Pipeline START: {paper_id} ===")

    # Stage 1
    report_stage(1)
    text_context = extract_text_from_pdf(pdf_path)

    # Stage 2 — parallel extraction
    report_stage(2)
    figures   = parse_figures(pdf_path)
    equations = extract_equations(pdf_path)
    tables    = extract_tables(pdf_path)

    # Stage 2 merge
    multimodal = merge_multimodal(text_context, figures, equations, tables)

    # Stage 3
    report_stage(3)
    ues = fuse_context(paper_id, text_context, multimodal)

    if PIPELINE_MODE == "generate_only":
        report_stage(4)
        repo_dir = generate_code(ues)
        logger.info(f"Code generated at {repo_dir}; execution and validation skipped.")
        return {
            "paper_id": paper_id,
            "mode": "generate_only",
            "validation_status": "skipped",
            "repo_dir": repo_dir,
            "fidelity_score": None,
            "passed": None,
            "error_report": None,
            "attempts": 1,
            "figures_extracted": len(figures),
            "equations_extracted": len(equations),
            "tables_extracted": len(tables),
        }

    from agents.stage5_executor_validator import execute_and_validate

    # Stage 4 + 5 with retry loop
    fidelity_score = 0.0
    passed = False

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(f"Attempt {attempt}/{MAX_RETRIES}")
        ues.retry_count = attempt - 1

        # Stage 4
        report_stage(4)
        repo_dir = generate_code(ues)

        # Stage 5
        report_stage(5)
        fidelity_score, error_report, passed = execute_and_validate(repo_dir, ues)

        if passed:
            logger.info(f"=== PASSED on attempt {attempt} ===")
            break

        if attempt < MAX_RETRIES:
            logger.warning(f"Attempt {attempt} failed. Retrying with error context.")
            ues.error_report = error_report
        else:
            logger.warning(f"All {MAX_RETRIES} attempts exhausted.")

    result = {
        "paper_id": paper_id,
        "mode": "full",
        "validation_status": "passed" if passed else "failed",
        "repo_dir": repo_dir,
        "fidelity_score": fidelity_score,
        "passed": passed,
        "error_report": error_report if not passed else None,
        "attempts": ues.retry_count + 1,
        "figures_extracted": len(figures),
        "equations_extracted": len(equations),
        "tables_extracted": len(tables),
    }

    logger.info(f"=== MRep Pipeline END: {paper_id} | Score: {fidelity_score:.2%} ===")
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python pipeline.py <pdf_path> <paper_id>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    paper_id = sys.argv[2]

    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)

    result = run_pipeline(pdf_path, paper_id)
    print("\n=== RESULT ===")
    for k, v in result.items():
        print(f"{k}: {v}")