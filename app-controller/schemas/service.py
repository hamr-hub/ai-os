from pydantic import BaseModel
from typing import Optional


class ServiceControlRequest(BaseModel):
    service_name: Optional[str] = None
