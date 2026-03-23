import asyncio
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DownloadStatus(str, Enum):
    IDLE = "idle"
    DOWNLOADING = "downloading"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class DownloadState:
    model_id: str
    status: DownloadStatus = DownloadStatus.IDLE
    progress: float = 0.0  # 0-100
    error: str | None = None


class ModelManager:
    """Manages model downloads in background threads."""

    def __init__(self):
        self._downloads: dict[str, DownloadState] = {}
        self._lock = threading.Lock()

    def get_download_state(self, model_id: str) -> DownloadState | None:
        with self._lock:
            return self._downloads.get(model_id)

    def all_downloads(self) -> dict[str, DownloadState]:
        with self._lock:
            return dict(self._downloads)

    def start_download(self, model_id: str) -> DownloadState:
        with self._lock:
            existing = self._downloads.get(model_id)
            if existing and existing.status == DownloadStatus.DOWNLOADING:
                return existing

            state = DownloadState(model_id=model_id, status=DownloadStatus.DOWNLOADING)
            self._downloads[model_id] = state

        thread = threading.Thread(
            target=self._download_worker, args=(model_id,), daemon=True
        )
        thread.start()
        logger.info(f"Started download for {model_id}")
        return state

    def _download_worker(self, model_id: str):
        try:
            from huggingface_hub import snapshot_download
            import os

            # Clean up any incomplete blobs first
            cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
            model_dir_name = f"models--{model_id.replace('/', '--')}"
            blobs_dir = os.path.join(cache_dir, model_dir_name, "blobs")
            if os.path.exists(blobs_dir):
                for f in os.listdir(blobs_dir):
                    if f.endswith(".incomplete"):
                        os.remove(os.path.join(blobs_dir, f))

            from zetesis_core.config import settings
            snapshot_download(model_id, token=settings.hf_token)

            with self._lock:
                self._downloads[model_id] = DownloadState(
                    model_id=model_id,
                    status=DownloadStatus.COMPLETE,
                    progress=100.0,
                )
            logger.info(f"Download complete: {model_id}")

        except Exception as e:
            logger.error(f"Download failed for {model_id}: {e}")
            with self._lock:
                self._downloads[model_id] = DownloadState(
                    model_id=model_id,
                    status=DownloadStatus.FAILED,
                    error=str(e),
                )


# Singleton
model_manager = ModelManager()
