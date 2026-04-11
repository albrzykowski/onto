from pydantic import BaseModel, Field


class JobRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[\w\-\.]+$")
    payload: dict = Field(default_factory=dict)