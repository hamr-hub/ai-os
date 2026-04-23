from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class TestRequest(BaseModel):
    model_name: str


class TestResponse(BaseModel):
    status: str
    message: str
    report: Optional[Dict[str, Any]] = None


class ComparativeAnalysisRequest(BaseModel):
    model_names: Optional[List[str]] = None
