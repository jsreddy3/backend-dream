"""Repository interface for daily check-ins."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime, date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from new_backend_ruminate.domain.checkin.entities import DailyCheckIn


class CheckInRepository(ABC):
    """Abstract repository for daily check-in operations."""
    
    @abstractmethod
    async def create_checkin(
        self,
        user_id: UUID,
        checkin: DailyCheckIn,
        session: AsyncSession
    ) -> DailyCheckIn:
        """Create a new check-in."""
        pass
    
    @abstractmethod
    async def get_checkin(
        self,
        user_id: UUID,
        checkin_id: UUID,
        session: AsyncSession
    ) -> Optional[DailyCheckIn]:
        """Get a specific check-in by ID."""
        pass
    
    @abstractmethod
    async def list_checkins_by_user(
        self,
        user_id: UUID,
        session: AsyncSession,
        limit: int = 10,
        offset: int = 0
    ) -> List[DailyCheckIn]:
        """List check-ins for a user."""
        pass
    
    @abstractmethod
    async def get_checkins_by_date_range(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
        session: AsyncSession
    ) -> List[DailyCheckIn]:
        """Get check-ins within a date range."""
        pass
    
    @abstractmethod
    async def update_insight(
        self,
        user_id: UUID,
        checkin_id: UUID,
        insight_text: str,
        context_metadata: dict,
        session: AsyncSession
    ) -> Optional[DailyCheckIn]:
        """Update the insight for a check-in."""
        pass
    
    @abstractmethod
    async def mark_insight_failed(
        self,
        user_id: UUID,
        checkin_id: UUID,
        error_message: str,
        session: AsyncSession
    ) -> Optional[DailyCheckIn]:
        """Mark insight generation as failed."""
        pass