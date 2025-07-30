"""Profile API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging

from new_backend_ruminate.dependencies import (
    get_session,
    get_profile_service,
    get_current_user_id,
)
from new_backend_ruminate.services.profile.service import ProfileService
from .schemas import ProfileRead, ProfileCalculateRequest, ProfileCalculateResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
)

# ─────────────────────────────── profile endpoints ─────────────────────────────── #

@router.get("/me/profile", response_model=ProfileRead, name="get_user_profile")
async def get_user_profile(
    user_id: UUID = Depends(get_current_user_id),
    svc: ProfileService = Depends(get_profile_service),
    db: AsyncSession = Depends(get_session),
):
    """Get the current user's profile."""
    profile = await svc.get_user_profile(user_id, db)
    
    if not profile:
        # Return minimal profile if none exists yet
        return ProfileRead(
            archetype=None,
            archetype_confidence=None,
            statistics={
                "total_dreams": 0,
                "total_duration_minutes": 0,
                "dream_streak_days": 0,
                "last_dream_date": None
            },
            emotional_metrics=[],
            dream_themes=[],
            recent_symbols=[],
            last_calculated_at=None,
            calculation_status="pending"
        )
    
    # Get dream summary for statistics
    summary = await svc.get_dream_summary(user_id, db)
    
    return ProfileRead(
        archetype=profile.archetype,
        archetype_confidence=profile.archetype_confidence,
        statistics={
            "total_dreams": summary.dream_count if summary else 0,
            "total_duration_minutes": (summary.total_duration_seconds // 60) if summary else 0,
            "dream_streak_days": summary.dream_streak_days if summary else 0,
            "last_dream_date": summary.last_dream_date if summary else None
        },
        emotional_metrics=[
            {"name": m.name, "intensity": m.intensity, "color": m.color}
            for m in profile.emotional_landscape
        ],
        dream_themes=[
            {"name": t.name, "percentage": t.percentage}
            for t in profile.top_themes
        ],
        recent_symbols=profile.recent_symbols,
        last_calculated_at=profile.last_calculated_at,
        calculation_status="completed" if profile.last_calculated_at else "pending"
    )

@router.post("/me/profile/calculate", response_model=ProfileCalculateResponse, name="calculate_user_profile")
async def calculate_user_profile(
    request: ProfileCalculateRequest,
    tasks: BackgroundTasks,
    user_id: UUID = Depends(get_current_user_id),
    svc: ProfileService = Depends(get_profile_service),
    db: AsyncSession = Depends(get_session),
):
    """Trigger profile calculation for the current user."""
    
    async def calculate_profile_task():
        """Background task to calculate profile."""
        try:
            async with db.begin():
                await svc.calculate_profile(user_id, db, force=request.force_recalculate)
                logger.info(f"Profile calculation completed for user {user_id}")
        except Exception as e:
            logger.error(f"Profile calculation failed for user {user_id}: {str(e)}")
    
    # Add task to background
    tasks.add_task(calculate_profile_task)
    
    return ProfileCalculateResponse(
        status="processing",
        message="Profile calculation has been queued"
    )