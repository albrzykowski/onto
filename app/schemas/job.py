import uuid
from pydantic import BaseModel, Field


class JobRequest(BaseModel):
    job_id: str | None = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique job ID for idempotency")
    tenant_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[\w\-\.]+$")
    payload: dict = Field(default_factory=dict)