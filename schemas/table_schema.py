from pydantic import BaseModel
from typing import List, Optional, Any

class Column(BaseModel):
    name: str
    unit: Optional[str] = None
    dtype: str = "float"

class TableSchema(BaseModel):
    table_id: str
    caption: Optional[str] = None
    columns: List[Column] = []
    row_labels: List[str] = []
    values: List[List[Any]] = []
    is_result_table: bool = False
    page_number: Optional[int] = None