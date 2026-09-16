from pydantic import BaseModel
from typing import List, Optional, Any

class Axis(BaseModel):
    label: str
    unit: Optional[str] = None
    values: Optional[List[Any]] = None
    min: Optional[float] = None
    max: Optional[float] = None

class Series(BaseModel):
    name: str
    data_points: List[List[float]]

class FigureData(BaseModel):
    figure_id: str
    chart_type: str
    title: Optional[str] = None
    x_axis: Optional[Axis] = None
    y_axis: Optional[Axis] = None
    series: List[Series] = []
    caption: Optional[str] = None
    page_number: Optional[int] = None
    extraction_confidence: float = 0.0