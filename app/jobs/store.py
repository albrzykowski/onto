"""Job status tracking storage."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import httpx

from app.config import HOST, PORT
from app.logger import get_logger

logger = get_logger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    tenant_id: str
    content: str
    status: JobStatus
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error: str | None = None
    result: dict | None = None


class JobStore:
    """In-memory job storage for API instance."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}

    def create(self, tenant_id: str, content: str, status: JobStatus = JobStatus.QUEUED) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            tenant_id=tenant_id,
            content=content,
            status=status,
        )
        self._jobs[job_id] = job
        logger.info(f"Created job {job_id} for tenant {tenant_id}")
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def update(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
        result: dict | None = None,
    ) -> Job | None:
        job = self._jobs.get(job_id)
        if job:
            job.status = status
            job.error = error
            job.result = result
            job.updated_at = datetime.utcnow()
            logger.info(f"Updated job {job_id} to {status}")
        return job


async def update_job_status(job_id: str, status: JobStatus, error: str | None = None, result: dict | None = None):
    """Update job status via internal API call (for consumer to use)."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://{HOST}:{PORT}/internal/jobs/{job_id}",
                json={"status": status.value, "error": error, "result": result},
                timeout=5.0,
            )
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to update job status: {e}")
        return False


# Global instance for simple in-memory storage
job_store = JobStore()