"""Job consumer."""
import json, time, os, urllib.request, pulsar
from app.config import PULSAR_URL, PULSAR_ADMIN, TOPIC_PREFIX
from app.logger import get_logger

logger = get_logger(__name__)

class Consumer:
    def __init__(self, interval=5):
        self.client, self.subs, self.cons, self.interval = None, f"consumer-{os.getpid()}", {}, interval

    def run(self):
        self.client = pulsar.Client(PULSAR_URL)
        while True:
            for t in self._topics():
                if t not in self.cons: self.cons[t] = self.client.subscribe(t, self.subs)
            for c in self.cons.values():
                try: msg = c.receive(1000); self._process(json.loads(msg.data())); c.acknowledge(msg)
                except pulsar.Timeout: pass
                except Exception as e: logger.error(f"Err: {e}")
            time.sleep(0.1)

    def _topics(self):
        try:
            with urllib.request.urlopen(f"{PULSAR_ADMIN}/admin/v2/persistent/public/default", timeout=5) as r:
                return [t for t in json.loads(r.read()) if f"{TOPIC_PREFIX}/tenant-" in t]
        except: return []

    def _process(self, d): logger.info(f"Job: {d.get('job_id')} for {d.get('tenant_id')}")