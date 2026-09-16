import fitz
import re
from loguru import logger
from typing import List
from sympy.parsing.latex import parse_latex
from schemas.equation_schema import EquationData

# Load optional OCR only when extraction actually runs.
_model = None
_ocr_initialized = False

def _load_ocr():
    global _model, _ocr_initialized
    if not _ocr_initialized:
        _ocr_initialized = True
        try:
            from pix2tex.cli import LatexOCR
            _model = LatexOCR()
        except Exception as exc:
            logger.warning(f"Pix2Tex unavailable; using text fallback: {exc}")
    return _model


def extract_equations(pdf_path: str) -> List[EquationData]:
    """
    Stage 2B: Extract equations from PDF.
    Returns list of EquationData objects with LaTeX and SymPy AST.
    """
    logger.info(f"Stage 2B: Extracting equations from {pdf_path}")
    doc = fitz.open(pdf_path)
    equations = []
    eq_count = 0

    for page_num, page in enumerate(doc):
        # Method 1: Extract inline LaTeX from text
        text = page.get_text("text")
        inline_eqs = _extract_inline_latex(text, page_num)
        equations.extend(inline_eqs)

        # Method 2: Extract equation images via Pix2Tex
        if _load_ocr() is not None:
            image_eqs = _extract_image_equations(doc, page, page_num)
            equations.extend(image_eqs)

        eq_count += len(inline_eqs)

    doc.close()
    logger.info(f"Stage 2B complete. {len(equations)} equations extracted.")
    return equations


def _extract_inline_latex(text: str, page_num: int) -> List[EquationData]:
    """Extract LaTeX equations embedded in text."""
    equations = []
    # Match display equations: $$ ... $$ or \[ ... \]
    patterns = [
        r"\$\$(.+?)\$\$",
        r"\\\[(.+?)\\\]",
        r"\\\((.+?)\\\)",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for i, match in enumerate(matches):
            latex_str = match.strip()
            sympy_expr = _latex_to_sympy(latex_str)
            eq = EquationData(
                equation_id=f"eq_inline_{page_num+1}_{len(equations)+1}",
                latex_str=latex_str,
                sympy_expr=sympy_expr,
                section_reference=f"page_{page_num+1}",
                extraction_confidence=0.8,
            )
            equations.append(eq)
    return equations


def _extract_image_equations(doc, page, page_num: int) -> List[EquationData]:
    """Extract equation images and run Pix2Tex on them."""
    equations = []
    try:
        from PIL import Image
        import io
        # Get page as image
        mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))

        # Pix2Tex on full page image
        latex_str = _model(img)
        if latex_str and len(latex_str) > 3:
            sympy_expr = _latex_to_sympy(latex_str)
            eq = EquationData(
                equation_id=f"eq_img_{page_num+1}",
                latex_str=latex_str,
                sympy_expr=sympy_expr,
                section_reference=f"page_{page_num+1}",
                extraction_confidence=0.7,
            )
            equations.append(eq)
    except Exception as e:
        logger.warning(f"Pix2Tex failed on page {page_num+1}: {e}")
    return equations


def _latex_to_sympy(latex_str: str) -> str:
    """Convert LaTeX string to SymPy expression string."""
    try:
        expr = parse_latex(latex_str)
        return str(expr)
    except Exception as e:
        logger.warning(f"LaTeX to SymPy failed for: {latex_str[:50]}... Error: {e}")
        return ""