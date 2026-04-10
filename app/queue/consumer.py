"""Job consumer - minimal."""
import json, time, os, urllib.request, pulsar
from app.config import PULSAR_URL
from app.logger import get_logger

logger = get_logger(__name__)

def get_topics():
    try:
        with urllib.request.urlopen("http://localhost:8080/admin/v2/persistent/public/default", timeout=5) as r:
            return [t for t in json.loads(r.read()) if "tenant-" in t]
    except: return []

def process(data):
    logger.info(f"Job: {data.get('job_id')} for {data.get('tenant_id')}")

def main():
    client = pulsar.Client(PULSAR_URL)
    subs = f"consumer-{os.getpid()}"
    cons = {}
    while True:
        for t in get_topics():
            if t not in cons: cons[t] = client.subscribe(t, subs)
        for c in cons.values():
            try: msg = c.receive(1000); process(json.loads(msg.data())); c.acknowledge(msg)
            except pulsar.Timeout: pass
            except Exception as e: logger.error(f"Error: {e}")
        time.sleep(0.1)

if __name__ == "__main__": main()
