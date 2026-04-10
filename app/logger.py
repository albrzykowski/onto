import logging
import sys
from app.config import LOG_LEVEL

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)