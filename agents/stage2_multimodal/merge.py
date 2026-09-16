from loguru import logger
from typing import List, Dict, Any
from schemas.figure_schema import FigureData
from schemas.equation_schema import EquationData
from schemas.table_schema import TableSchema

def merge_multimodal(
    text_context: Dict[str, Any],
    figures: List[FigureData],
    equations: List[EquationData],
    tables: List[TableSchema],
) -> Dict[str, Any]:
    """
    Merge all Stage 2 sub-agent outputs into a single
    MultimodalContentObject ready for Stage 3.
    """
    logger.info("Stage 2 merge: combining figures, equations, tables")

    # Attach captions only when a page has an unambiguous one-to-one match.
    # IDs encode page/image indexes, not the paper's printed figure numbers.
    for items, caption_key in ((figures, "figure_captions"), (tables, "table_captions")):
        for item in items:
            if item.caption:
                continue
            page_items = [other for other in items if other.page_number == item.page_number]
            captions = [caption for caption in text_context.get(caption_key, [])
                        if caption.get("page") == item.page_number]
            if len(page_items) == 1 and len(captions) == 1:
                item.caption = captions[0]["caption"]

    logger.info(
        f"Merge complete: {len(figures)} figures, "
        f"{len(equations)} equations, {len(tables)} tables"
    )

    return {
        "figures": figures,
        "equations": equations,
        "tables": tables,
    }