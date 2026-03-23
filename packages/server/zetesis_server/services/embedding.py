import asyncio
import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model: all-MiniLM-L6-v2")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _encode_sync(text: str) -> list[float]:
    model = _get_model()
    embedding = model.encode(text, show_progress_bar=False)
    return embedding.tolist()


async def generate_embedding(text: str) -> list[float]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _encode_sync, text)
