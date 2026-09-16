"""
Stage 2A — Figure Parser (Groq Vision)
========================================
Extracts figures from a PDF via PyMuPDF, resizes them to fit the Groq Vision
API payload limit, then sends each image to the configured GROQ_VISION_MODEL
for structured data extraction.

Provider: Groq Vision
Model:    configured via GROQ_VISION_MODEL (.env)
Format:   base64 PNG in image_url content part

Image pipeline:
  PDF page  -->  PyMuPDF (extract_image)  -->  PIL resize (<=512px)
  -->  base64 PNG  -->  Groq Vision  -->  JSON parse  -->  FigureData

Error codes produced:
  GROQ_VISION_MODEL_UNAVAILABLE
  GROQ_VISION_AUTH_FAILED
  GROQ_VISION_RATE_LIMITED
  GROQ_VISION_TRUNCATED
  GROQ_VISION_INVALID_JSON
  GROQ_VISION_SCHEMA_INVALID
  GROQ_VISION_REQUEST_FAILED
"""

from __future__ import annotations

import base64
import io
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import fitz                          # PyMuPDF
from groq import Groq
from loguru import logger
from PIL import Image
from pydantic import ValidationError

from config import (
    GROQ_API_KEY,
    GROQ_VISION_MAX_DIM,
    GROQ_VISION_MAX_TOKENS,
    GROQ_VISION_MODEL,
    SUPPORTED_FIGURE_TYPES,
    validate_vision_model,
)
from schemas.figure_schema import Axis, FigureData, Series


# ── Prompt ───────────────────────────────────────────────────────────────────

FIGURE_PROMPT = """\
You are a scientific chart data extractor.

Analyze the supplied scientific figure carefully.

Return ONLY valid JSON matching the schema below. Do NOT include any explanation,
markdown code fences, or extra text — only the JSON object.

Schema:
{
  "chart_type": "line_chart | bar_chart | confusion_matrix | training_curve | other",
  "title": "<chart title or null>",
  "x_axis": {"label": "<str>", "unit": "<str or null>", "values": [<list or null>]},
  "y_axis": {"label": "<str>", "unit": "<str or null>", "min": <float or null>, "max": <float or null>},
  "series": [{"name": "<str>", "data_points": [[x, y], ...]}],
  "caption": "<visible caption text or null>",
  "extraction_confidence": <float 0.0-1.0>
}

Rules:
- Do not hallucinate data points. Only extract values clearly visible in the figure.
- If chart_type cannot be determined, use "other".
- If a field cannot be read from the image, use null.
- data_points must be [[x_value, y_value], ...] pairs of numbers.
- extraction_confidence reflects your confidence in the extracted data (1.0 = very clear).
"""


# ── Image utilities ───────────────────────────────────────────────────────────

def _resize_image(img_bytes: bytes, max_dim: int = GROQ_VISION_MAX_DIM) -> Tuple[str, bytes]:
    """
    Resize the image so that max(width, height) <= max_dim.
    Returns ("png", resized_png_bytes).
    The Groq Vision API rejects very large base64 payloads (~>100 KB base64).
    """
    img = Image.open(io.BytesIO(img_bytes))
    # Convert RGBA / P mode to RGB to ensure PNG compatibility
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "png", buf.getvalue()


# ── JSON parsing helpers ──────────────────────────────────────────────────────

def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to extract a JSON object from raw LLM output.
    Strips markdown fences if present.
    Does NOT use regex reconstruction — raises ValueError if not parseable.
    """
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    # Find the first { ... } block
    start = cleaned.find("{")
    if start == -1:
        return None
    # Find the last matching closing brace
    depth = 0
    end = -1
    for i, ch in enumerate(cleaned[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        return None
    return json.loads(cleaned[start:end])


# ── Schema builder ────────────────────────────────────────────────────────────

def _build_figure_data(
    fig_id: str,
    parsed: Dict[str, Any],
    page_num: int,
) -> FigureData:
    """Build a validated FigureData from a parsed Groq Vision response."""
    x_raw = parsed.get("x_axis") or {}
    y_raw = parsed.get("y_axis") or {}
    series_raw = parsed.get("series") or []

    series: List[Series] = []
    for s in series_raw:
        try:
            series.append(Series(
                name=str(s.get("name", "")),
                data_points=[[float(p[0]), float(p[1])] for p in (s.get("data_points") or [])
                             if isinstance(p, (list, tuple)) and len(p) == 2],
            ))
        except Exception:
            pass  # Skip malformed series

    x_axis: Optional[Axis] = None
    if x_raw:
        try:
            x_axis = Axis(**{k: v for k, v in x_raw.items() if k in Axis.model_fields})
        except Exception:
            x_axis = None

    y_axis: Optional[Axis] = None
    if y_raw:
        try:
            y_axis = Axis(**{k: v for k, v in y_raw.items() if k in Axis.model_fields})
        except Exception:
            y_axis = None

    return FigureData(
        figure_id=fig_id,
        chart_type=parsed.get("chart_type", "other"),
        title=parsed.get("title"),
        x_axis=x_axis,
        y_axis=y_axis,
        series=series,
        caption=parsed.get("caption"),
        page_number=page_num,
        extraction_confidence=float(parsed.get("extraction_confidence") or 0.5),
        provider="groq",
        vision_model=GROQ_VISION_MODEL,
    )


# ── Groq Vision call ──────────────────────────────────────────────────────────

def _call_groq_vision(image_b64: str, ext: str, fig_id: str) -> Dict[str, Any]:
    """
    Send a single image to Groq Vision and return the parsed JSON dict.

    Returns {} on any failure — each failure is logged with a structured error code
    so the caller can record the exact reason per-figure.

    Error codes logged:
      GROQ_VISION_RATE_LIMITED
      GROQ_VISION_TRUNCATED
      GROQ_VISION_INVALID_JSON
      GROQ_VISION_SCHEMA_INVALID
      GROQ_VISION_REQUEST_FAILED
    """
    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": FIGURE_PROMPT},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/{ext};base64,{image_b64}"
                    }},
                ],
            }],
            max_tokens=GROQ_VISION_MAX_TOKENS,
            temperature=0.0,
        )
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "rate_limit" in err_str.lower():
            logger.warning(f"[GROQ_VISION_RATE_LIMITED] {fig_id}: {err_str[:200]}")
        elif "401" in err_str or "auth" in err_str.lower():
            logger.warning(f"[GROQ_VISION_AUTH_FAILED] {fig_id}: {err_str[:200]}")
        else:
            logger.warning(f"[GROQ_VISION_REQUEST_FAILED] {fig_id}: {err_str[:200]}")
        return {}

    choice = response.choices[0]
    finish = choice.finish_reason

    if finish == "length":
        logger.warning(
            f"[GROQ_VISION_TRUNCATED] {fig_id}: response truncated at "
            f"{response.usage.completion_tokens} tokens (limit={GROQ_VISION_MAX_TOKENS})"
        )
        return {}

    raw = (choice.message.content or "").strip()
    if not raw:
        logger.warning(f"[GROQ_VISION_INVALID_JSON] {fig_id}: empty response body")
        return {}

    try:
        parsed = _extract_json(raw)
        if parsed is None:
            raise ValueError("No JSON object found in response")
        return parsed
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"[GROQ_VISION_INVALID_JSON] {fig_id}: {exc} — raw={raw[:120]}")
        return {}


# ── Public API ────────────────────────────────────────────────────────────────

def parse_figures(pdf_path: str) -> List[FigureData]:
    """
    Stage 2A: Extract all figures from a PDF using PyMuPDF, then analyse each
    image with Groq Vision to produce structured FigureData.

    Each figure is processed independently.  A vision failure on one figure
    does not prevent other figures from being processed.

    Returns a list of FigureData.  Failed figures are recorded with
    vision_error set; they are still returned so downstream stages can see
    which figures were attempted.

    Status reporting:
      All structured  → figures.status = PASS
      Some failed     → figures.status = DEGRADED
      All failed / no figures → figures.status = FAILED
    """
    logger.info(f"Stage 2A: Parsing figures from {pdf_path}")

    # Validate vision model configuration before any PDF work
    try:
        validate_vision_model()
    except ValueError as exc:
        logger.error(f"Stage 2A aborted: {exc}")
        raise

    doc = fitz.open(pdf_path)
    figures: List[FigureData] = []
    detected_count = 0
    extracted_count = 0
    vision_sent_count = 0
    structured_count = 0
    failed_count = 0

    for page_num, page in enumerate(doc):
        image_list = page.get_images(full=True)
        for img_idx, img in enumerate(image_list):
            try:
                xref = img[0]
                base_image = doc.extract_image(xref)
                orig_w = base_image["width"]
                orig_h = base_image["height"]

                # Skip tiny images (icons, decorations)
                if orig_w < 100 or orig_h < 100:
                    continue

                detected_count += 1
                fig_id = f"fig_{page_num + 1}_{img_idx + 1}"

                # ── Image extraction (PyMuPDF) ──
                raw_bytes = base_image["image"]
                extracted_count += 1
                logger.debug(
                    f"  Extracted {fig_id}: {orig_w}x{orig_h}px "
                    f"({base_image['ext']})"
                )

                # ── Resize for API ──
                resized_ext, resized_bytes = _resize_image(raw_bytes, GROQ_VISION_MAX_DIM)
                image_b64 = base64.b64encode(resized_bytes).decode("utf-8")

                # ── Groq Vision call ──
                vision_sent_count += 1
                logger.info(
                    f"Stage 2A: Sending {fig_id} to Groq Vision "
                    f"({GROQ_VISION_MODEL}, b64_size={len(image_b64)} chars)"
                )
                parsed = _call_groq_vision(image_b64, resized_ext, fig_id)

                if not parsed:
                    # Vision failed but image extraction succeeded;
                    # record a degraded FigureData with vision_error
                    failed_count += 1
                    figures.append(FigureData(
                        figure_id=fig_id,
                        chart_type="other",
                        page_number=page_num + 1,
                        provider="groq",
                        vision_model=GROQ_VISION_MODEL,
                        vision_error="GROQ_VISION_FAILED — see log for detail",
                        extraction_confidence=0.0,
                    ))
                    continue

                # ── Build validated FigureData ──
                try:
                    figure = _build_figure_data(fig_id, parsed, page_num + 1)
                    structured_count += 1
                    figures.append(figure)
                    logger.info(
                        f"  {fig_id}: chart_type={figure.chart_type}, "
                        f"series={len(figure.series)}, "
                        f"confidence={figure.extraction_confidence:.2f}"
                    )
                except (ValidationError, Exception) as exc:
                    failed_count += 1
                    logger.warning(
                        f"[GROQ_VISION_SCHEMA_INVALID] {fig_id}: {exc}"
                    )
                    figures.append(FigureData(
                        figure_id=fig_id,
                        chart_type="other",
                        page_number=page_num + 1,
                        provider="groq",
                        vision_model=GROQ_VISION_MODEL,
                        vision_error=f"GROQ_VISION_SCHEMA_INVALID: {exc}",
                        extraction_confidence=0.0,
                    ))

            except Exception as exc:
                logger.warning(
                    f"Stage 2A: Figure extraction failed on page {page_num + 1}, "
                    f"img {img_idx}: {exc}"
                )
                continue

    doc.close()

    # ── Status summary ──
    if detected_count == 0:
        status = "FAILED"
    elif failed_count == 0:
        status = "PASS"
    elif structured_count == 0:
        status = "FAILED"
    else:
        status = "DEGRADED"

    logger.info(
        f"Stage 2A complete. "
        f"detected={detected_count}, extracted={extracted_count}, "
        f"sent_to_vision={vision_sent_count}, "
        f"structured={structured_count}, failed={failed_count} "
        f"[status={status}]"
    )

    # Attach stage-level metadata to allow orchestrator to build status report
    parse_figures._last_stats = {
        "status": status,
        "provider": "groq",
        "model": GROQ_VISION_MODEL,
        "detected": detected_count,
        "extracted": extracted_count,
        "sent_to_vision": vision_sent_count,
        "structured": structured_count,
        "failed": failed_count,
    }

    return figures