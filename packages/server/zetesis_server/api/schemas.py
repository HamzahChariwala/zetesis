from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from zetesis_core.enums import OutputStatus, RequestStatus, RequestType, ReviewAction


class CreateRequestBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    request_type: RequestType
    tags: list[str] = []
    context: str | None = None
    priority: int = Field(default=0, ge=0, le=10)
    model_id: str | None = None
    tools: list[str] = []


class RequestResponse(BaseModel):
    id: UUID
    query: str
    request_type: RequestType
    tags: list[str]
    context: str | None
    priority: int
    model_id: str | None
    tools: list[str]
    status: RequestStatus
    parent_id: UUID | None
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OutputResponse(BaseModel):
    id: UUID
    request_id: UUID
    content: str
    model_id: str
    status: OutputStatus
    inference_time_ms: int | None
    token_count: int | None
    truncated: bool = False
    rating: int | None = None
    metadata: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewRequestBody(BaseModel):
    action: ReviewAction
    comment: str | None = None
    follow_up_query: str | None = None


class ReviewResponse(BaseModel):
    id: UUID
    output_id: UUID
    action: ReviewAction
    comment: str | None
    follow_up_request_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RateBody(BaseModel):
    rating: int = Field(..., ge=1, le=5)


class QueueStatusResponse(BaseModel):
    queued: int
    processing: int
    completed: int
    failed: int


class SimilarOutputResponse(BaseModel):
    output: OutputResponse
    score: float
    query: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: bool
