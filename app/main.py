import signal
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.routes import router, shutdown
from app.config import HOST, PORT
from app.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application started")
    yield
    shutdown()


app = FastAPI(title="Job Queue Service", lifespan=lifespan)
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)