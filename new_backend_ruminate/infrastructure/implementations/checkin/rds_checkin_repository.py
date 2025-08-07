"""PostgreSQL implementation of CheckInRepository."""
from __future__ import annotations
from typing import List, Optional
from datetime import datetime, date
from uuid import UUID

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from new_backend_ruminate.domain.checkin.entities import DailyCheckIn, InsightStatus
from new_backend_ruminate.domain.checkin.repo import CheckInRepository


class RDSCheckInRepository(CheckInRepository):
    """PostgreSQL implementation of check-in repository."""
    
    async def create_checkin(
        self,
        user_id: UUID,
        checkin: DailyCheckIn,
        session: AsyncSession
    ) -> DailyCheckIn:
        """Create a new check-in."""
        try:
            checkin.user_id = user_id
            session.add(checkin)
            await session.commit()
            await session.refresh(checkin)
            return checkin
        except IntegrityError:
            await session.rollback()
            # If duplicate, return existing (idempotent)
            return await self.get_checkin(user_id, checkin.id, session)
    
    async def get_checkin(
        self,
        user_id: UUID,
        checkin_id: UUID,
        session: AsyncSession
    ) -> Optional[DailyCheckIn]:
        """Get a specific check-in by ID."""
        stmt = select(DailyCheckIn).where(
            and_(
                DailyCheckIn.id == checkin_id,
                DailyCheckIn.user_id == user_id
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_checkins_by_user(
        self,
        user_id: UUID,
        session: AsyncSession,
        limit: int = 10,
        offset: int = 0
    ) -> List[DailyCheckIn]:
        """List check-ins for a user, ordered by creation date descending."""
        stmt = (
            select(DailyCheckIn)
            .where(DailyCheckIn.user_id == user_id)
            .order_by(DailyCheckIn.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_checkins_by_date_range(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
        session: AsyncSession
    ) -> List[DailyCheckIn]:
        """Get check-ins within a date range."""
        # Convert dates to datetime for comparison
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        stmt = (
            select(DailyCheckIn)
            .where(
                and_(
                    DailyCheckIn.user_id == user_id,
                    DailyCheckIn.created_at >= start_datetime,
                    DailyCheckIn.created_at <= end_datetime
                )
            )
            .order_by(DailyCheckIn.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def update_insight(
        self,
        user_id: UUID,
        checkin_id: UUID,
        insight_text: str,
        context_metadata: dict,
        session: AsyncSession
    ) -> Optional[DailyCheckIn]:
        """Update the insight for a check-in."""
        stmt = (
            update(DailyCheckIn)
            .where(
                and_(
                    DailyCheckIn.id == checkin_id,
                    DailyCheckIn.user_id == user_id
                )
            )
            .values(
                insight_text=insight_text,
                insight_status=InsightStatus.COMPLETED.value,
                insight_generated_at=datetime.utcnow(),
                context_metadata=context_metadata
            )
            .returning(DailyCheckIn)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.scalar_one_or_none()
    
    async def mark_insight_failed(
        self,
        user_id: UUID,
        checkin_id: UUID,
        error_message: str,
        session: AsyncSession
    ) -> Optional[DailyCheckIn]:
        """Mark insight generation as failed."""
        # First get the current retry count
        checkin = await self.get_checkin(user_id, checkin_id, session)
        if not checkin:
            return None
        
        stmt = (
            update(DailyCheckIn)
            .where(
                and_(
                    DailyCheckIn.id == checkin_id,
                    DailyCheckIn.user_id == user_id
                )
            )
            .values(
                insight_status=InsightStatus.FAILED.value,
                error_message=error_message,
                retry_count=checkin.retry_count + 1
            )
            .returning(DailyCheckIn)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.scalar_one_or_none()