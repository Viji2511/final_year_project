from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from schemas.figure_schema import FigureData
from schemas.equation_schema import EquationData
from schemas.table_schema import TableSchema

class BaselineComparison(BaseModel):
    model_name: str
    metric: str
    value: float

class UES(BaseModel):
    paper_id: str
    arxiv_id: Optional[str] = None
    title: Optional[str] = None
    task: Optional[str] = None
    dataset: Optional[str] = None
    model_architecture: Optional[str] = None
    hyperparameters: Dict[str, Any] = {}
    loss_function: Optional[EquationData] = None
    evaluation_metrics: List[EquationData] = []
    figures: List[FigureData] = []
    result_tables: List[TableSchema] = []
    training_procedure: Optional[str] = None
    baseline_comparisons: List[BaselineComparison] = []
    methodology_text: Optional[str] = None
    algorithms: List[str] = []
    retry_count: int = 0
    error_report: Optional[str] = None