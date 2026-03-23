from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from zetesis_core.enums import RequestStatus
from zetesis_server.db.models import OutputRow, RequestRow


class QueueManager:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def recover_stuck(self) -> int:
        """Reset any requests stuck in 'processing' back to 'queued'.
        Called on startup to recover from crashes."""
        async with self._session_factory() as db:
            stmt = (
                update(RequestRow)
                .where(RequestRow.status == RequestStatus.PROCESSING.value)
                .values(status=RequestStatus.QUEUED.value, updated_at=datetime.utcnow())
            )
            result = await db.execute(stmt)
            await db.commit()
            return result.rowcount

    async def dequeue(self) -> RequestRow | None:
        async with self._session_factory() as db:
            stmt = (
                select(RequestRow)
                .where(RequestRow.status == RequestStatus.QUEUED.value)
                .order_by(RequestRow.priority.desc(), RequestRow.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None

            row.status = RequestStatus.PROCESSING.value
            row.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(row)
            return row

    async def complete(self, request_id: UUID, output: OutputRow) -> None:
        async with self._session_factory() as db:
            stmt = (
                update(RequestRow)
                .where(RequestRow.id == request_id)
                .values(status=RequestStatus.COMPLETED.value, updated_at=datetime.utcnow())
            )
            await db.execute(stmt)
            db.add(output)
            await db.commit()

    async def fail(self, request_id: UUID, error: str) -> None:
        async with self._session_factory() as db:
            stmt = (
                update(RequestRow)
                .where(RequestRow.id == request_id)
                .values(
                    status=RequestStatus.FAILED.value,
                    error=error,
                    updated_at=datetime.utcnow(),
                )
            )
            await db.execute(stmt)
            await db.commit()
