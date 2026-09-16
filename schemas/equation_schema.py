from pydantic import BaseModel
from typing import Optional

class EquationData(BaseModel):
    equation_id: str
    latex_str: str
    sympy_expr: Optional[str] = None   # string repr of SymPy expr
    section_reference: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    extraction_confidence: float = 0.0