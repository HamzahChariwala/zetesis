from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from zetesis_core.enums import OutputStatus
from zetesis_server.api.schemas import OutputResponse, RateBody
from zetesis_server.db.engine import get_db
from zetesis_server.db.models import OutputRow
from zetesis_server.db.repository import OutputRepository

router = APIRouter(prefix="/outputs", tags=["outputs"])


@router.get("", response_model=list[OutputResponse])
async def list_outputs(
    status: OutputStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    repo = OutputRepository(db)
    rows = await repo.list(status=status, limit=limit, offset=offset)
    return [_to_response(r) for r in rows]


@router.get("/{output_id}", response_model=OutputResponse)
async def get_output(output_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = OutputRepository(db)
    row = await repo.get(output_id)
    if not row:
        raise HTTPException(status_code=404, detail="Output not found")
    return _to_response(row)


@router.patch("/{output_id}/rate", response_model=OutputResponse)
async def rate_output(output_id: UUID, body: RateBody, db: AsyncSession = Depends(get_db)):
    repo = OutputRepository(db)
    row = await repo.get(output_id)
    if not row:
        raise HTTPException(status_code=404, detail="Output not found")
    await repo.update_rating(output_id, body.rating)
    row = await repo.get(output_id)
    return _to_response(row)


def _to_response(row: OutputRow) -> OutputResponse:
    return OutputResponse(
        id=row.id,
        request_id=row.request_id,
        content=row.content,
        model_id=row.model_id,
        status=OutputStatus(row.status),
        inference_time_ms=row.inference_time_ms,
        token_count=row.token_count,
        truncated=row.truncated,
        rating=row.rating,
        metadata=row.metadata_ or {},
        created_at=row.created_at,
    )
