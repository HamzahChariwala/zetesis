from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from zetesis_core.config import settings
from zetesis_server.api.schemas import HealthResponse, QueueStatusResponse
from zetesis_server.db.engine import get_db
from zetesis_server.db.models import RequestRow
from zetesis_server.services.model_manager import model_manager

AVAILABLE_MODELS = [
    {"id": "mlx-community/Qwen2.5-7B-Instruct-4bit", "label": "Qwen 2.5 7B (fast)", "size_gb": 4},
    {"id": "mlx-community/Qwen2.5-32B-Instruct-4bit", "label": "Qwen 2.5 32B", "size_gb": 18},
    {"id": "mlx-community/Qwen2.5-72B-Instruct-4bit", "label": "Qwen 2.5 72B", "size_gb": 40},
    {"id": "mlx-community/Qwen3-32B-4bit", "label": "Qwen 3 32B", "size_gb": 18},
    {"id": "mlx-community/Qwen3.5-27B-4bit", "label": "Qwen 3.5 27B", "size_gb": 15},
]

AVAILABLE_MODEL_IDS = {m["id"] for m in AVAILABLE_MODELS}

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)):
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return HealthResponse(status="ok" if db_ok else "degraded", database=db_ok)


@router.get("/models")
async def list_models():
    from zetesis_inference.mlx_backend import MLXBackend

    downloads = model_manager.all_downloads()
    models = []
    for m in AVAILABLE_MODELS:
        downloaded = MLXBackend._is_model_cached(m["id"])
        dl_state = downloads.get(m["id"])
        download_info = None
        if dl_state:
            download_info = {
                "status": dl_state.status.value,
                "progress": dl_state.progress,
                "error": dl_state.error,
            }
        models.append({
            **m,
            "downloaded": downloaded,
            "download": download_info,
        })

    return {
        "default": settings.inference_model,
        "models": models,
    }


class DownloadRequest(BaseModel):
    model_id: str


@router.post("/models/download")
async def download_model(body: DownloadRequest):
    if body.model_id not in AVAILABLE_MODEL_IDS:
        raise HTTPException(status_code=400, detail=f"Unknown model: {body.model_id}")

    from zetesis_inference.mlx_backend import MLXBackend
    if MLXBackend._is_model_cached(body.model_id):
        return {"status": "already_downloaded", "model_id": body.model_id}

    state = model_manager.start_download(body.model_id)
    return {
        "status": state.status.value,
        "model_id": body.model_id,
    }


@router.get("/tools")
async def list_tools():
    from zetesis_inference.tools.definitions import TOOL_DEFINITIONS
    return {
        "tools": [
            {"name": name, "description": defn["function"]["description"]}
            for name, defn in TOOL_DEFINITIONS.items()
        ]
    }


@router.get("/queue/status", response_model=QueueStatusResponse)
async def queue_status(db: AsyncSession = Depends(get_db)):
    stmt = select(RequestRow.status, func.count()).group_by(RequestRow.status)
    result = await db.execute(stmt)
    counts = {row[0]: row[1] for row in result.all()}
    return QueueStatusResponse(
        queued=counts.get("queued", 0),
        processing=counts.get("processing", 0),
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
    )
