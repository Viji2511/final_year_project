import fitz
import base64
import json
import re
from loguru import logger
from typing import List
from openai import OpenAI
from config import OPENAI_API_KEY, GPT4V_MODEL, SUPPORTED_FIGURE_TYPES
from schemas.figure_schema import FigureData, Axis, Series



FIGURE_PROMPT = """
You are a scientific chart data extractor.
Given this chart image, return ONLY valid JSON with no explanation.

Schema:
{
  "chart_type": "line_chart | bar_chart | confusion_matrix | training_curve | other",
  "title": "chart title or null",
  "x_axis": {"label": str, "unit": str or null, "values": [] or null},
  "y_axis": {"label": str, "unit": str or null, "min": float or null, "max": float or null},
  "series": [{"name": str, "data_points": [[x, y], ...]}],
  "caption": "figure caption if visible or null",
  "extraction_confidence": 0.0 to 1.0
}

Rules:
- Do not hallucinate data points. Only extract values clearly visible in the chart.
- If chart_type is "other" or unreadable, still return the schema with null values.
- data_points should be [[x_value, y_value], ...] pairs.
"""


def parse_figures(pdf_path: str) -> List[FigureData]:
    """
    Stage 2A: Extract all figures from PDF and parse with GPT-4o Vision.
    Returns list of FigureData objects.
    """
    logger.info(f"Stage 2A: Parsing figures from {pdf_path}")
    doc = fitz.open(pdf_path)
    figures = []
    fig_count = 0

    for page_num, page in enumerate(doc):
        image_list = page.get_images(full=True)
        for img_idx, img in enumerate(image_list):
            try:
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                img_ext = base_image["ext"]

                # Skip tiny images (icons, logos)
                if base_image["width"] < 100 or base_image["height"] < 100:
                    continue

                fig_id = f"fig_{page_num+1}_{img_idx+1}"
                parsed = _call_gpt4v(image_b64, img_ext, fig_id)

                if parsed and parsed.get("chart_type") in SUPPORTED_FIGURE_TYPES:
                    figure = _build_figure_data(fig_id, parsed, page_num + 1)
                    figures.append(figure)
                    fig_count += 1

            except Exception as e:
                logger.warning(f"Figure extraction failed on page {page_num+1}, img {img_idx}: {e}")
                continue

    doc.close()
    logger.info(f"Stage 2A complete. {fig_count} supported figures extracted.")
    return figures


def _call_gpt4v(image_b64: str, ext: str, fig_id: str) -> dict:
    """Call GPT-4o Vision with the figure image."""
    try:
        response = OpenAI(api_key=OPENAI_API_KEY).chat.completions.create(
            model=GPT4V_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": FIGURE_PROMPT},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/{ext};base64,{image_b64}",
                        "detail": "high"
                    }}
                ]
            }],
            max_tokens=1000,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"GPT-4o Vision call failed for {fig_id}: {e}")
        return {}


def _build_figure_data(fig_id: str, parsed: dict, page_num: int) -> FigureData:
    """Build a FigureData object from GPT-4o response."""
    x = parsed.get("x_axis") or {}
    y = parsed.get("y_axis") or {}
    series_raw = parsed.get("series") or []

    series = [
        Series(name=s.get("name", ""), data_points=s.get("data_points", []))
        for s in series_raw
    ]

    return FigureData(
        figure_id=fig_id,
        chart_type=parsed.get("chart_type", "other"),
        title=parsed.get("title"),
        x_axis=Axis(**x) if x else None,
        y_axis=Axis(**y) if y else None,
        series=series,
        caption=parsed.get("caption"),
        page_number=page_num,
        extraction_confidence=parsed.get("extraction_confidence", 0.5),
    )