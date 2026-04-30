"""API routes."""
import socket

from fastapi import APIRouter, HTTPException, status

from app.config import PULSAR_URL, TOPIC_PREFIX
from app.jobs.store import JobStatus, job_store
from app.logger import get_logger
from app.queue.producer import Producer, PulsarConnectionError
from app.schemas.document import DocumentRequest

router = APIRouter()
log = get_logger(__name__)
producer = Producer()


@router.get("/health")
def health(): return {"status": "healthy"}


@router.get("/ready")
def ready():
    try:
        h, p = PULSAR_URL.replace("pulsar://", "").split(":")
        s = socket.socket(); s.settimeout(1); s.connect((h, int(p))); s.close()
        return {"status": "ready", "pulsar": "connected"}
    except Exception as e:
        log.error(f"Readiness failed: {e}")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail={"status": "not ready", "error": str(e)})


@router.post("/documents")
def create_document(doc: DocumentRequest):
    job = None
    try:
        # Create job tracking first
        job = job_store.create(tenant_id=doc.tenant_id, content=doc.content)

        # Send to Pulsar (include job_id in message)
        topic = f"{TOPIC_PREFIX}/tenant-{doc.tenant_id}"
        producer.send(topic=topic, msg={**doc.model_dump(), "job_id": job.job_id})

        return {"job_id": job.job_id, "status": "accepted", "tenant_id": doc.tenant_id}
    except PulsarConnectionError as e:
        log.error(f"Pulsar unavailable: {e}")
        # Update job status to failed
        if job:
            job_store.update(job.job_id, JobStatus.FAILED, error=str(e))
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail={"status": "failed", "error": str(e)})
    except Exception as e:
        log.error(f"Failed: {e}")
        if job:
            job_store.update(job.job_id, JobStatus.FAILED, error=str(e))
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"status": "failed", "error": str(e)})


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"error": "Job not found"})
    return {
        "job_id": job.job_id,
        "tenant_id": job.tenant_id,
        "status": job.status.value,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "error": job.error,
        "result": job.result,
    }


# Internal endpoint for consumer to update job status
@router.post("/internal/jobs/{job_id}")
def update_job_internal(job_id: str, data: dict):
    """Internal endpoint for updating job status from consumer."""
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"error": "Job not found"})
    job_status = data.get("status")
    if job_status:
        job_store.update(job_id, JobStatus(job_status), error=data.get("error"), result=data.get("result"))
    return {"status": "updated"}


def shutdown(): producer.close()