import asyncio
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from zetesis_core.config import settings
from zetesis_server.api.routes_outputs import router as outputs_router
from zetesis_server.api.routes_requests import router as requests_router
from zetesis_server.api.routes_review import router as review_router
from zetesis_server.api.routes_knowledge import router as knowledge_router
from zetesis_server.api.routes_system import router as system_router
from zetesis_server.db.engine import async_session
from zetesis_server.queue.manager import QueueManager
from zetesis_server.queue.worker import InferenceWorker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import here to avoid loading MLX at import time
    from zetesis_inference.mlx_backend import MLXBackend

    # Fix #1: Recover requests stuck in "processing" from a previous crash
    queue = QueueManager(session_factory=async_session)
    recovered = await queue.recover_stuck()
    if recovered:
        logger.info(f"Recovered {recovered} stuck request(s) back to queued")

    logger.info(f"Loading inference backend: {settings.inference_backend}")
    backend = MLXBackend(model_path=settings.inference_model)
    worker = InferenceWorker(queue=queue, backend=backend)

    worker_task = asyncio.create_task(worker.run())
    logger.info("InferenceWorker task created")

    yield

    worker.stop()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("InferenceWorker stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Zetesis", version="0.1.0", docs_url="/docs", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(requests_router, prefix="/api/v1")
    app.include_router(outputs_router, prefix="/api/v1")
    app.include_router(review_router, prefix="/api/v1")
    app.include_router(knowledge_router, prefix="/api/v1")
    app.include_router(system_router, prefix="/api/v1")

    return app


app = create_app()
