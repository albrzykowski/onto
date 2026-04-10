from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import uuid


class JobRequest(BaseModel):
    job_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique job ID for idempotency")
    tenant_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[\w\-\.]+$")
    payload: Dict[str, Any] = Field(default_factory=dict)