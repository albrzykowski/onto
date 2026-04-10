from pydantic import BaseModel
from typing import Dict, Any


class JobRequest(BaseModel):
    tenant_id: str
    payload: Dict[str, Any]
