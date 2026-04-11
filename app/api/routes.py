"""API routes."""
import socket

from fastapi import APIRouter, HTTPException, status

from app.config import PULSAR_URL, TOPIC_PREFIX
from app.logger import get_logger
from app.queue.producer import Producer
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
    try:
        topic = f"{TOPIC_PREFIX}/tenant-{doc.tenant_id}"
        producer.send(topic=topic, msg=doc.model_dump())
        return {"status": "accepted", "tenant_id": doc.tenant_id}
    except Exception as e:
        log.error(f"Failed: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"status": "failed", "error": str(e)})


def shutdown(): producer.close()