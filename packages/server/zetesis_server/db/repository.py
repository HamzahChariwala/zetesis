from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from zetesis_core.enums import OutputStatus, RequestStatus
from zetesis_server.db.models import OutputRow, RequestRow, ReviewRow


class RequestRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, row: RequestRow) -> RequestRow:
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def get(self, request_id: UUID) -> RequestRow | None:
        return await self.db.get(RequestRow, request_id)

    async def list(
        self,
        status: RequestStatus | None = None,
        request_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RequestRow]:
        stmt = select(RequestRow).order_by(RequestRow.created_at.desc())
        if status:
            stmt = stmt.where(RequestRow.status == status.value)
        if request_type:
            stmt = stmt.where(RequestRow.type == request_type)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def retry(self, request_id: UUID) -> bool:
        stmt = (
            update(RequestRow)
            .where(RequestRow.id == request_id, RequestRow.status == RequestStatus.FAILED.value)
            .values(status=RequestStatus.QUEUED.value, error=None)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def cancel(self, request_id: UUID) -> bool:
        stmt = (
            update(RequestRow)
            .where(RequestRow.id == request_id, RequestRow.status == RequestStatus.QUEUED.value)
            .values(status=RequestStatus.FAILED.value, error="Cancelled by user")
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0


class OutputRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, row: OutputRow) -> OutputRow:
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def get(self, output_id: UUID) -> OutputRow | None:
        return await self.db.get(OutputRow, output_id)

    async def list(
        self,
        status: OutputStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[OutputRow]:
        stmt = select(OutputRow).order_by(OutputRow.created_at.desc())
        if status:
            stmt = stmt.where(OutputRow.status == status.value)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_since(self, since: datetime) -> list[OutputRow]:
        stmt = (
            select(OutputRow)
            .where(OutputRow.created_at > since)
            .order_by(OutputRow.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_rating(self, output_id: UUID, rating: int) -> bool:
        stmt = update(OutputRow).where(OutputRow.id == output_id).values(rating=rating)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def update_status(self, output_id: UUID, status: OutputStatus) -> bool:
        stmt = update(OutputRow).where(OutputRow.id == output_id).values(status=status.value)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0


class ReviewRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, row: ReviewRow) -> ReviewRow:
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def list_for_output(self, output_id: UUID) -> list[ReviewRow]:
        stmt = (
            select(ReviewRow)
            .where(ReviewRow.output_id == output_id)
            .order_by(ReviewRow.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
