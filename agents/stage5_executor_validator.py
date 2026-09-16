import os
import subprocess
import json
import re
import uuid
from loguru import logger
from typing import Dict, Any, Tuple
from config import (
    DOCKER_CPU, DOCKER_RAM, DOCKER_TIMEOUT,
    FIDELITY_TOLERANCE, SSIM_THRESHOLD, SANDBOX_DIR
)
from schemas.ues_schema import UES

def execute_and_validate(repo_dir: str, ues: UES) -> Tuple[float, str, bool]:
    """
    Stage 5: Run generated repo in Docker sandbox.
    Returns (fidelity_score, error_report, passed).
    """
    logger.info(f"Stage 5: Executing repository at {repo_dir}")

    # Build Docker image
    image_tag = f"mrep_{ues.paper_id}".lower().replace(" ", "_")
    build_success = _build_docker_image(repo_dir, image_tag)

    if not build_success:
        return 0.0, "Docker build failed", False

    # Run container
    output, error, timed_out = _run_docker_container(image_tag)

    if timed_out:
        return 0.0, "Execution timed out (4 hour limit)", False

    if error:
        return 0.0, f"Runtime error: {error[:500]}", False

    # Parse output metrics
    output_metrics = _parse_output_metrics(output)

    # Compare against UES target values
    fidelity_score, mismatch_details = _compare_metrics(output_metrics, ues)

    passed = fidelity_score >= (1.0 - FIDELITY_TOLERANCE)

    if passed:
        logger.info(f"Stage 5: PASSED with fidelity score {fidelity_score:.2%}")
        return fidelity_score, "", True
    else:
        error_report = _build_error_report(mismatch_details, error, output_metrics)
        logger.warning(f"Stage 5: FAILED with fidelity score {fidelity_score:.2%}")
        return fidelity_score, error_report, False


def _build_docker_image(repo_dir: str, image_tag: str) -> bool:
    """Copy Dockerfile to repo and build image."""
    try:
        dockerfile_src = os.path.join(SANDBOX_DIR, "Dockerfile")
        dockerfile_dst = os.path.join(repo_dir, "Dockerfile")
        import shutil
        shutil.copy(dockerfile_src, dockerfile_dst)

        result = subprocess.run(
            ["docker", "build", "-t", image_tag, repo_dir],
            capture_output=True, text=True, timeout=600
        )
        if result.returncode != 0:
            logger.error(f"Docker build failed: {result.stderr[:500]}")
            return False
        return True
    except Exception as e:
        logger.error(f"Docker build exception: {e}")
        return False


def _run_docker_container(image_tag: str) -> Tuple[str, str, bool]:
    """Run Docker container with resource limits."""
    container_name = "mrep-" + uuid.uuid4().hex
    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm", "--name", container_name,
                f"--cpus={DOCKER_CPU}",
                f"--memory={DOCKER_RAM}",
                image_tag,
                "bash", "run.sh"
            ],
            capture_output=True, text=True,
            timeout=DOCKER_TIMEOUT
        )
        return result.stdout, (f"Exit code {result.returncode}: {result.stderr}" if result.returncode else ""), False
    except subprocess.TimeoutExpired:
        try:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=30)
        except Exception as exc:
            logger.warning(f"Container cleanup failed: {exc}")
        return "", "Timeout", True
    except Exception as e:
        return "", str(e), False


def _parse_output_metrics(output: str) -> Dict[str, float]:
    """Parse metric values from container stdout."""
    metrics = {}
    pattern = r"([A-Za-z_]\w*)\s*[:=]\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
    for key, value in re.findall(pattern, output):
        metrics[key.lower()] = float(value)
    return metrics


def _compare_metrics(
    output_metrics: Dict[str, float], ues: UES
) -> Tuple[float, list]:
    """Compare output metrics to UES target values."""
    if not ues.baseline_comparisons:
        return 0.0, [{"reason": "No target metrics extracted; reproduction cannot be verified."}]

    passed = 0
    total = 0
    mismatches = []

    for baseline in ues.baseline_comparisons:
        metric_key = baseline.metric.lower().replace(" ", "_")
        total += 1
        if metric_key in output_metrics:
            actual = output_metrics[metric_key]
            expected = baseline.value
            tolerance = abs(expected * FIDELITY_TOLERANCE)
            if abs(actual - expected) <= tolerance:
                passed += 1
            else:
                mismatches.append({
                    "metric": baseline.metric,
                    "expected": expected,
                    "actual": actual,
                    "model": baseline.model_name,
                })

        else:
            mismatches.append({"metric": baseline.metric, "expected": baseline.value, "actual": None, "model": baseline.model_name})

    score = passed / total if total > 0 else 0.0
    return score, mismatches


def _build_error_report(mismatches, stderr, output_metrics) -> str:
    """Build structured error report for Stage 4 retry."""
    return json.dumps({
        "failed_metrics": mismatches,
        "stderr": stderr[:300] if stderr else "",
        "output_metrics_found": output_metrics,
        "instruction": "Fix the above metric mismatches. Check loss function implementation and evaluation code."
    }, indent=2)