from pydantic import BaseModel, Field


class DocumentRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[\w\-\.]+$")
    content: str