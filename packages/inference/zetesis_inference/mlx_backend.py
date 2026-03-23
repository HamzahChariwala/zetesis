import asyncio
import gc
import logging
import time

from zetesis_core.interfaces import BackendHealth, InferenceBackend
from zetesis_core.models import GenerationParams, GenerationResult
from zetesis_inference.registry import BackendRegistry

logger = logging.getLogger(__name__)


@BackendRegistry.register("mlx")
class MLXBackend(InferenceBackend):
    def __init__(self, model_path: str, max_memory_gb: float = 80.0):
        self._model_path = model_path
        self._max_memory_gb = max_memory_gb
        self._model = None
        self._tokenizer = None
        self._loaded_model_path: str | None = None

    @staticmethod
    def _is_model_cached(model_path: str) -> bool:
        """Check if a HuggingFace model is fully downloaded locally."""
        try:
            from pathlib import Path
            from huggingface_hub import scan_cache_dir

            cache = scan_cache_dir()
            for repo in cache.repos:
                if repo.repo_id == model_path:
                    # Check that no blob files are incomplete
                    blobs_dir = Path(repo.repo_path) / "blobs"
                    if blobs_dir.exists():
                        incomplete = list(blobs_dir.glob("*.incomplete"))
                        if incomplete:
                            return False
                    # Check we have at least one safetensors file
                    for rev in repo.revisions:
                        has_weights = any(
                            f.file_name.endswith(".safetensors")
                            for f in rev.files
                        )
                        if has_weights:
                            return True
            return False
        except Exception:
            return False

    def _load_model(self, model_path: str):
        import mlx.core as mx
        import mlx_lm

        if self._loaded_model_path == model_path and self._model is not None:
            return

        # Check if model is cached before attempting to load
        if not self._is_model_cached(model_path):
            raise RuntimeError(
                f"Model '{model_path}' is not downloaded yet. "
                f"Download it first with: uv run python -c \"from huggingface_hub import snapshot_download; snapshot_download('{model_path}')\""
            )

        # Unload current model if switching
        if self._model is not None:
            logger.info(f"Unloading model: {self._loaded_model_path}")
            del self._model
            del self._tokenizer
            self._model = None
            self._tokenizer = None
            gc.collect()
            mx.metal.clear_cache()

        logger.info(f"Loading model: {model_path}")
        self._model, self._tokenizer = mlx_lm.load(model_path)
        self._loaded_model_path = model_path
        logger.info(f"Model loaded: {model_path}")

    def _generate_sync(
        self,
        messages: list[dict[str, str]],
        params: GenerationParams,
        model_path: str | None = None,
        tools: list[dict] | None = None,
    ) -> GenerationResult:
        import mlx_lm
        from mlx_lm.sample_utils import make_sampler

        target_model = model_path or self._model_path
        self._load_model(target_model)

        template_kwargs = {"tokenize": False, "add_generation_prompt": True}
        if tools:
            template_kwargs["tools"] = tools

        prompt = self._tokenizer.apply_chat_template(messages, **template_kwargs)

        sampler = make_sampler(temp=params.temperature, top_p=params.top_p)
        start = time.monotonic()
        response = mlx_lm.generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=params.max_tokens,
            sampler=sampler,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        token_count = len(self._tokenizer.encode(response))
        return GenerationResult(
            text=response,
            token_count=token_count,
            inference_time_ms=elapsed_ms,
            model_id=target_model,
        )

    async def generate(
        self,
        messages: list[dict[str, str]],
        params: GenerationParams,
        model_path: str | None = None,
        tools: list[dict] | None = None,
    ) -> GenerationResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._generate_sync, messages, params, model_path, tools
        )

    async def health(self) -> BackendHealth:
        import mlx.core as mx

        mem = mx.metal.get_active_memory() / (1024**3)
        total = mx.metal.get_peak_memory() / (1024**3)
        return BackendHealth(
            available=True,
            model_loaded=self._model is not None,
            memory_used_gb=round(mem, 2),
            memory_total_gb=round(max(total, self._max_memory_gb), 2),
        )

    def model_id(self) -> str:
        return self._loaded_model_path or self._model_path
