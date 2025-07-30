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
from new_backend_ruminate.services.profile.service import ProfileService, ARCHETYPES
from .schemas import ProfileRead, ProfileCalculateRequest, ProfileCalculateResponse
from .preference_schemas import PreferencesCreate, PreferencesUpdate, PreferencesRead

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
    
    # Check if archetype needs migration (for display purposes)
    display_archetype = profile.archetype
    if profile.archetype in svc.ARCHETYPE_MIGRATION:
        display_archetype = svc.ARCHETYPE_MIGRATION[profile.archetype]
    
    return ProfileRead(
        archetype=display_archetype,
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

# ─────────────────────────────── preferences endpoints ─────────────────────────────── #

@router.get("/me/preferences", response_model=PreferencesRead, name="get_user_preferences")
async def get_user_preferences(
    user_id: UUID = Depends(get_current_user_id),
    svc: ProfileService = Depends(get_profile_service),
    db: AsyncSession = Depends(get_session),
):
    """Get the current user's preferences."""
    preferences = await svc.get_user_preferences(user_id, db)
    
    if not preferences:
        # Return default preferences if none exist
        raise HTTPException(
            status_code=404,
            detail="No preferences found. Please complete onboarding first."
        )
    
    return preferences

@router.post("/me/preferences", response_model=PreferencesRead, status_code=201, name="create_user_preferences")
async def create_user_preferences(
    preferences: PreferencesCreate,
    user_id: UUID = Depends(get_current_user_id),
    svc: ProfileService = Depends(get_profile_service),
    db: AsyncSession = Depends(get_session),
):
    """Create user preferences (typically during onboarding)."""
    # Check if preferences already exist
    existing = await svc.get_user_preferences(user_id, db)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Preferences already exist. Use PATCH to update."
        )
    
    # Create preferences
    preferences_data = preferences.dict(exclude_unset=True)
    
    # Create preferences
    created = await svc.create_user_preferences(user_id, preferences_data, db)
    
    return created

@router.patch("/me/preferences", response_model=PreferencesRead, name="update_user_preferences")
async def update_user_preferences(
    preferences: PreferencesUpdate,
    user_id: UUID = Depends(get_current_user_id),
    svc: ProfileService = Depends(get_profile_service),
    db: AsyncSession = Depends(get_session),
):
    """Update user preferences (partial update supported)."""
    # Get only set fields
    preferences_data = preferences.dict(exclude_unset=True)
    
    if not preferences_data:
        raise HTTPException(
            status_code=400,
            detail="No fields to update"
        )
    
    updated = await svc.update_user_preferences(user_id, preferences_data, db)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Preferences not found"
        )
    
    return updated

@router.post("/me/preferences/suggest-archetype", name="suggest_archetype")
async def suggest_archetype(
    user_id: UUID = Depends(get_current_user_id),
    svc: ProfileService = Depends(get_profile_service),
    db: AsyncSession = Depends(get_session),
):
    """Suggest an archetype based on current preferences."""
    preferences = await svc.get_user_preferences(user_id, db)
    if not preferences:
        raise HTTPException(
            status_code=404,
            detail="No preferences found"
        )
    
    archetype, confidence = await svc.suggest_initial_archetype(preferences)
    
    archetype_info = ARCHETYPES.get(archetype, {})
    
    return {
        "suggested_archetype": archetype,
        "confidence": confidence,
        "archetype_details": {
            "name": archetype_info.get("name", archetype.title()),
            "symbol": archetype_info.get("symbol", "🧠"),
            "description": archetype_info.get("description", ""),
            "researcher": archetype_info.get("researcher", ""),
            "theory": archetype_info.get("theory", "")
        }
    }

@router.post("/me/profile/initial-archetype", name="save_initial_archetype")
async def save_initial_archetype(
    request: dict,
    user_id: UUID = Depends(get_current_user_id),
    svc: ProfileService = Depends(get_profile_service),
    db: AsyncSession = Depends(get_session),
):
    """Save the initial archetype after onboarding."""
    archetype = request.get("archetype")
    confidence = request.get("confidence", 0.85)
    
    if not archetype:
        raise HTTPException(
            status_code=400,
            detail="Archetype is required"
        )
    
    # Save the initial archetype to the user's profile
    profile = await svc.save_initial_archetype(user_id, archetype, confidence, db)
    
    return {
        "message": "Initial archetype saved successfully",
        "archetype": profile.archetype,
        "confidence": profile.archetype_confidence
    }