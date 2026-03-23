from abc import ABC, abstractmethod

from pydantic import BaseModel

from zetesis_core.models import GenerationParams, GenerationResult


class BackendHealth(BaseModel):
    available: bool
    model_loaded: bool
    memory_used_gb: float
    memory_total_gb: float


class InferenceBackend(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict[str, str]], params: GenerationParams, model_path: str | None = None, tools: list[dict] | None = None) -> GenerationResult:
        ...

    @abstractmethod
    async def health(self) -> BackendHealth:
        ...

    @abstractmethod
    def model_id(self) -> str:
        ...
