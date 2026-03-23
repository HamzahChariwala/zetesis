from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from zetesis_core.enums import OutputStatus, RequestType, ReviewAction
from zetesis_server.api.schemas import ReviewRequestBody, ReviewResponse
from zetesis_server.db.engine import get_db
from zetesis_server.db.models import OutputRow, RequestRow, ReviewRow
from zetesis_server.db.repository import OutputRepository, RequestRepository, ReviewRepository

router = APIRouter(prefix="/outputs", tags=["review"])


@router.post("/{output_id}/review", response_model=ReviewResponse, status_code=201)
async def review_output(
    output_id: UUID, body: ReviewRequestBody, db: AsyncSession = Depends(get_db)
):
    output_repo = OutputRepository(db)
    output = await output_repo.get(output_id)
    if not output:
        raise HTTPException(status_code=404, detail="Output not found")

    follow_up_request_id = None

    if body.action == ReviewAction.APPROVE:
        await output_repo.update_status(output_id, OutputStatus.APPROVED)

    elif body.action == ReviewAction.DELETE:
        await output_repo.update_status(output_id, OutputStatus.DELETED)

    elif body.action == ReviewAction.FOLLOW_UP:
        if not body.follow_up_query:
            raise HTTPException(status_code=400, detail="follow_up_query required for follow-up")
        request_repo = RequestRepository(db)
        original_request = await request_repo.get(output.request_id)
        follow_up_context = f"Previous output:\n{output.content}"
        if original_request and original_request.context:
            follow_up_context = f"{original_request.context}\n\n{follow_up_context}"
        follow_up = RequestRow(
            query=body.follow_up_query,
            type=original_request.type if original_request else RequestType.DEEP_DIVE.value,
            tags=original_request.tags if original_request else [],
            context=follow_up_context,
            parent_id=output.request_id,
        )
        follow_up = await request_repo.create(follow_up)
        follow_up_request_id = follow_up.id

    review_repo = ReviewRepository(db)
    review = ReviewRow(
        output_id=output_id,
        action=body.action.value,
        comment=body.comment,
        follow_up_request_id=follow_up_request_id,
    )
    review = await review_repo.create(review)

    return ReviewResponse(
        id=review.id,
        output_id=review.output_id,
        action=ReviewAction(review.action),
        comment=review.comment,
        follow_up_request_id=review.follow_up_request_id,
        created_at=review.created_at,
    )


@router.get("/{output_id}/reviews", response_model=list[ReviewResponse])
async def list_reviews(output_id: UUID, db: AsyncSession = Depends(get_db)):
    review_repo = ReviewRepository(db)
    rows = await review_repo.list_for_output(output_id)
    return [
        ReviewResponse(
            id=r.id,
            output_id=r.output_id,
            action=ReviewAction(r.action),
            comment=r.comment,
            follow_up_request_id=r.follow_up_request_id,
            created_at=r.created_at,
        )
        for r in rows
    ]
