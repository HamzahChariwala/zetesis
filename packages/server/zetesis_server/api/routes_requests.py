from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from zetesis_core.enums import RequestStatus, RequestType
from zetesis_server.api.schemas import CreateRequestBody, RequestResponse
from zetesis_server.db.engine import get_db
from zetesis_server.db.models import RequestRow
from zetesis_server.db.repository import RequestRepository

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("", response_model=RequestResponse, status_code=201)
async def create_request(body: CreateRequestBody, db: AsyncSession = Depends(get_db)):
    repo = RequestRepository(db)
    row = RequestRow(
        query=body.query,
        type=body.request_type.value,
        tags=body.tags,
        context=body.context,
        priority=body.priority,
        model_id=body.model_id,
        tools=body.tools,
    )
    row = await repo.create(row)
    return _to_response(row)


@router.get("", response_model=list[RequestResponse])
async def list_requests(
    status: RequestStatus | None = None,
    request_type: RequestType | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    repo = RequestRepository(db)
    rows = await repo.list(
        status=status,
        request_type=request_type.value if request_type else None,
        limit=limit,
        offset=offset,
    )
    return [_to_response(r) for r in rows]


@router.get("/{request_id}", response_model=RequestResponse)
async def get_request(request_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = RequestRepository(db)
    row = await repo.get(request_id)
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    return _to_response(row)


@router.post("/{request_id}/retry", response_model=RequestResponse)
async def retry_request(request_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = RequestRepository(db)
    retried = await repo.retry(request_id)
    if not retried:
        raise HTTPException(status_code=404, detail="Request not found or not in failed state")
    row = await repo.get(request_id)
    return _to_response(row)


@router.delete("/{request_id}", status_code=204)
async def cancel_request(request_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = RequestRepository(db)
    cancelled = await repo.cancel(request_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Request not found or not cancellable")


def _to_response(row: RequestRow) -> RequestResponse:
    return RequestResponse(
        id=row.id,
        query=row.query,
        request_type=RequestType(row.type),
        tags=row.tags or [],
        context=row.context,
        priority=row.priority,
        model_id=row.model_id,
        tools=row.tools or [],
        status=RequestStatus(row.status),
        parent_id=row.parent_id,
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
