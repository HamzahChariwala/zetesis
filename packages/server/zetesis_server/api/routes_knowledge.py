from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from zetesis_core.enums import OutputStatus
from zetesis_server.api.schemas import OutputResponse, SimilarOutputResponse
from zetesis_server.db.engine import get_db
from zetesis_server.db.models import OutputRow
from zetesis_server.services.embedding import generate_embedding

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _build_response(row) -> SimilarOutputResponse:
    return SimilarOutputResponse(
        output=OutputResponse(
            id=row["id"],
            request_id=row["request_id"],
            content=row["content"],
            model_id=row["model_id"],
            status=OutputStatus(row["status"]),
            inference_time_ms=row["inference_time_ms"],
            token_count=row["token_count"],
            truncated=row["truncated"],
            metadata=row["metadata"] or {},
            created_at=row["created_at"],
        ),
        score=round(row["score"], 4),
        query=row["request_query"],
    )


@router.get("/search", response_model=list[SimilarOutputResponse])
async def search_knowledge(
    q: str = Query(..., min_length=1),
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Semantic search across all outputs that have embeddings."""
    query_embedding = await generate_embedding(q)
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    stmt = text("""
        SELECT o.id, o.request_id, o.content, o.model_id, o.status,
               o.inference_time_ms, o.token_count, o.truncated, o.metadata,
               o.created_at,
               1 - (o.embedding <=> CAST(:embedding AS vector)) as score,
               r.query as request_query
        FROM outputs o
        JOIN requests r ON r.id = o.request_id
        WHERE o.embedding IS NOT NULL
        ORDER BY o.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)

    result = await db.execute(stmt, {"embedding": embedding_str, "limit": limit})
    return [_build_response(row) for row in result.mappings().all()]


@router.get("/{output_id}/similar", response_model=list[SimilarOutputResponse])
async def find_similar(
    output_id: UUID,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Find outputs most similar to a given output, ranked by cosine similarity."""
    source = await db.get(OutputRow, output_id)
    if not source:
        raise HTTPException(status_code=404, detail="Output not found")
    if source.embedding is None:
        raise HTTPException(status_code=400, detail="Output has no embedding")

    embedding_str = "[" + ",".join(str(x) for x in source.embedding) + "]"

    stmt = text("""
        SELECT o.id, o.request_id, o.content, o.model_id, o.status,
               o.inference_time_ms, o.token_count, o.truncated, o.metadata,
               o.created_at,
               1 - (o.embedding <=> CAST(:embedding AS vector)) as score,
               r.query as request_query
        FROM outputs o
        JOIN requests r ON r.id = o.request_id
        WHERE o.embedding IS NOT NULL
          AND o.id != :source_id
        ORDER BY o.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)

    result = await db.execute(
        stmt, {"embedding": embedding_str, "source_id": output_id, "limit": limit}
    )
    return [_build_response(row) for row in result.mappings().all()]
