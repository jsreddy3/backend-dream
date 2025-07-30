"""Repository interface for user profiles and dream summaries."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .profile import DreamSummary, UserProfile


class ProfileRepository(ABC):
    """Abstract repository for user profiles and dream summaries."""
    
    # Dream Summary methods
    @abstractmethod
    async def get_dream_summary(self, user_id: UUID, session: AsyncSession) -> Optional[DreamSummary]:
        """Get dream summary for a user."""
        ...
    
    @abstractmethod
    async def create_dream_summary(self, summary: DreamSummary, session: AsyncSession) -> DreamSummary:
        """Create a new dream summary."""
        ...
    
    @abstractmethod
    async def update_dream_summary(self, summary: DreamSummary, session: AsyncSession) -> DreamSummary:
        """Update an existing dream summary."""
        ...
    
    @abstractmethod
    async def get_or_create_dream_summary(self, user_id: UUID, session: AsyncSession) -> DreamSummary:
        """Get existing dream summary or create a new one."""
        ...
    
    # User Profile methods
    @abstractmethod
    async def get_user_profile(self, user_id: UUID, session: AsyncSession) -> Optional[UserProfile]:
        """Get user profile."""
        ...
    
    @abstractmethod
    async def create_user_profile(self, profile: UserProfile, session: AsyncSession) -> UserProfile:
        """Create a new user profile."""
        ...
    
    @abstractmethod
    async def update_user_profile(self, profile: UserProfile, session: AsyncSession) -> UserProfile:
        """Update an existing user profile."""
        ...
    
    @abstractmethod
    async def get_or_create_user_profile(self, user_id: UUID, session: AsyncSession) -> UserProfile:
        """Get existing user profile or create a new one."""
        ...