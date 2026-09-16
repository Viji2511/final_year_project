import fitz  # PyMuPDF
import re
import json
from loguru import logger
from typing import Dict, Any
from config import GROQ_API_KEY, GROQ_MODEL
from groq import Groq



SECTION_KEYWORDS = [
    "abstract", "introduction", "related work",
    "methodology", "method", "approach",
    "experiments", "experimental setup", "results",
    "conclusion", "references"
]

def extract_text_from_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Stage 1: Extract structured text from paper PDF.
    Returns a dict with sections, hyperparams, algorithms, captions.
    """
    logger.info(f"Stage 1: Extracting text from {pdf_path}")
    doc = fitz.open(pdf_path)
    full_text = ""
    figure_captions = []
    table_captions  = []

    for page_num, page in enumerate(doc):
        text = page.get_text("text")
        full_text += f"\n[PAGE {page_num + 1}]\n{text}"

        # Extract figure and table captions
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if re.match(r"^(Figure|Fig\.)\s*\d+", line, re.IGNORECASE):
                figure_captions.append({
                    "label": re.match(r"^(Figure|Fig\.)\s*\d+", line, re.IGNORECASE).group(),
                    "caption": line,
                    "page": page_num + 1
                })
            if re.match(r"^Table\s*\d+", line, re.IGNORECASE):
                table_captions.append({
                    "label": re.match(r"^Table\s*\d+", line, re.IGNORECASE).group(),
                    "caption": line,
                    "page": page_num + 1
                })

    doc.close()

    # Use LLM to extract structured info
    structured = _extract_structured_with_llm(full_text[:12000])  # token limit
    structured["figure_captions"] = figure_captions
    structured["table_captions"]  = table_captions
    structured["full_text"]        = full_text

    logger.info(f"Stage 1 complete. Sections found: {list(structured.get('sections', {}).keys())}")
    return structured


def _extract_structured_with_llm(text: str) -> Dict[str, Any]:
    """Use Groq LLM to extract hyperparams, algorithms, and sections."""
    prompt = f"""
You are a scientific paper parser. Extract the following from this paper text and return ONLY valid JSON.

Extract:
1. title: paper title
2. abstract: abstract text
3. methodology: methodology/method section text
4. hyperparameters: dict of all hyperparameter names and values found (learning rate, batch size, epochs, optimizer, etc.)
5. algorithms: list of algorithm descriptions found
6. task: what ML task this paper addresses (classification, detection, generation, etc.)
7. dataset: dataset name(s) used
8. model_architecture: brief description of model architecture

Return ONLY this JSON structure, no explanation:
{{
  "title": "",
  "abstract": "",
  "methodology": "",
  "hyperparameters": {{}},
  "algorithms": [],
  "task": "",
  "dataset": "",
  "model_architecture": ""
}}

Paper text:
{text}
"""
    try:
        response = Groq(api_key=GROQ_API_KEY).chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content.strip()
        # Clean markdown fences if present
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception as e:
        logger.error(f"Stage 1 LLM extraction failed: {e}")
        return {
            "title": "", "abstract": "", "methodology": "",
            "hyperparameters": {}, "algorithms": [],
            "task": "", "dataset": "", "model_architecture": ""
        }