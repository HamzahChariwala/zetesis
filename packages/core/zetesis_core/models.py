from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from zetesis_core.enums import OutputStatus, RequestStatus, RequestType, ReviewAction


class ResearchRequest(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    query: str
    request_type: RequestType
    tags: list[str] = []
    context: str | None = None
    priority: int = 0
    status: RequestStatus = RequestStatus.QUEUED
    parent_id: UUID | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GenerationParams(BaseModel):
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    stop_sequences: list[str] = []


class GenerationResult(BaseModel):
    text: str
    token_count: int
    inference_time_ms: int
    model_id: str


class ResearchOutput(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    content: str
    model_id: str
    status: OutputStatus = OutputStatus.UNCHECKED
    inference_time_ms: int = 0
    token_count: int = 0
    metadata: dict = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    output_id: UUID
    action: ReviewAction
    comment: str | None = None
    follow_up_request_id: UUID | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
