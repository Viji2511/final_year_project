import fitz
import pdfplumber
from loguru import logger
from typing import List
from schemas.table_schema import TableSchema, Column

def extract_tables(pdf_path: str) -> List[TableSchema]:
    """
    Stage 2C: Extract tables from PDF using pdfplumber.
    Returns list of TableSchema objects.
    """
    logger.info(f"Stage 2C: Extracting tables from {pdf_path}")
    tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            try:
                raw_tables = page.extract_tables()
                for t_idx, raw_table in enumerate(raw_tables):
                    if not raw_table or len(raw_table) < 2:
                        continue
                    schema = _build_table_schema(
                        raw_table, page_num + 1, t_idx + 1
                    )
                    if schema:
                        tables.append(schema)
            except Exception as e:
                logger.warning(f"Table extraction failed on page {page_num+1}: {e}")
                continue

    logger.info(f"Stage 2C complete. {len(tables)} tables extracted.")
    return tables


def _build_table_schema(
    raw_table: list, page_num: int, t_idx: int
) -> TableSchema:
    """Convert raw pdfplumber table into typed TableSchema."""
    try:
        headers = raw_table[0]
        rows    = raw_table[1:]

        # Clean headers
        headers = [str(h).strip() if h else f"col_{i}"
                   for i, h in enumerate(headers)]

        columns = [Column(name=h, dtype=_infer_dtype(rows, i))
                   for i, h in enumerate(headers)]

        row_labels = [str(r[0]).strip() if r else "" for r in rows]
        values = []
        for row in rows:
            row_vals = []
            for cell in row:
                try:
                    row_vals.append(float(str(cell).replace("%", "").strip()))
                except Exception:
                    row_vals.append(str(cell).strip() if cell else "")
            values.append(row_vals)

        is_result = _is_result_table(headers)

        return TableSchema(
            table_id=f"table_{page_num}_{t_idx}",
            columns=columns,
            row_labels=row_labels,
            values=values,
            is_result_table=is_result,
            page_number=page_num,
        )
    except Exception as e:
        logger.warning(f"Table schema build failed: {e}")
        return None


def _infer_dtype(rows: list, col_idx: int) -> str:
    """Infer column dtype from values."""
    for row in rows[:5]:
        if col_idx < len(row) and row[col_idx]:
            try:
                float(str(row[col_idx]).replace("%", "").strip())
                return "float"
            except Exception:
                return "str"
    return "str"


def _is_result_table(headers: list) -> bool:
    """Heuristic: result tables have metric-like column names."""
    metric_keywords = [
        "accuracy", "f1", "precision", "recall", "auc",
        "bleu", "rouge", "map", "ap", "score", "loss",
        "error", "top-1", "top-5", "perplexity", "cer", "wer"
    ]
    headers_lower = [h.lower() for h in headers]
    return any(kw in h for h in headers_lower for kw in metric_keywords)