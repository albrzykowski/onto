from fastapi import APIRouter
from app.schemas.job import JobRequest
from app.queue.producer import QueueProducer

router = APIRouter()
producer = QueueProducer()


@router.post("/jobs")
def create_job(job: JobRequest):
    topic = f"persistent://public/default/tenant-{job.tenant_id}"

    producer.send(
        topic=topic,
        message=job.dict()
    )

    return {
        "status": "accepted",
        "tenant_id": job.tenant_id
    }
