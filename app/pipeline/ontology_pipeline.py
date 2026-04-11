from app.logger import get_logger

logger = get_logger(__name__)

class OntologyPipeline:
    async def process(self, msg: dict):
        logger.info(f"Document for tenant: {msg.get('tenant_id')}, content: {msg.get('content')}")