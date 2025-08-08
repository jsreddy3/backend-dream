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
    get_user_repository,
)
from new_backend_ruminate.services.profile.service import ProfileService, ARCHETYPES
from new_backend_ruminate.services.astrology.birth_chart_service import BirthChartService
from .schemas import (
    ProfileRead, ProfileCalculateRequest, ProfileCalculateResponse,
    ArchetypeRead, DailyMessageRead, BirthChartRequest, BirthChartResponse, 
    BirthChartRequestAdvanced
)
from .preference_schemas import PreferencesCreate, PreferencesUpdate, PreferencesRead
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
)


def generate_daily_message(archetype_id: str) -> DailyMessageRead:
    """Generate a daily message based on archetype and date."""
    archetype_data = ARCHETYPES.get(archetype_id)
    if not archetype_data:
        return None
        
    # For now, use day of year to select message
    # Later: Can make this more sophisticated with user context
    day_of_year = datetime.now().timetuple().tm_yday
    
    # Create a pool of messages based on archetype
    # This is placeholder - in real implementation, these would be more diverse
    messages = [
        {
            "analytical": [
                ("Tonight your brain organizes today's challenges, making tomorrow's tasks clearer.",
                 "Interpretation inspired by psychologist Dr. Ernest Hartmann's research on memory consolidation during dreams."),
                ("Your dreams may subtly rehearse practical scenarios tonight, enhancing tomorrow's problem-solving skills.",
                 "Based on psychologist Dr. Antti Revonsuo's threat-simulation theory of dreaming."),
                ("Tonight's dreams integrate new information quietly. Tomorrow, note any improved clarity or understanding.",
                 "Guided by sleep researcher Dr. Robert Stickgold's studies on learning and dream integration.")
            ],
            "reflective": [
                ("Tonight your dreams may gently process emotions, helping you wake up feeling clearer.",
                 "Inspired by dream researcher Dr. Rosalind Cartwright's work on dreams and emotional resilience."),
                ("Dreams tonight could reflect interpersonal dynamics. Tomorrow, consider new emotional insights.",
                 "Based on psychologist Dr. Calvin Hall's studies of relationships and dream content."),
                ("Your dreams may explore deep feelings tonight, guiding emotional adaptation and balance.",
                 "Influenced by psychiatrist Dr. Milton Kramer's theory of dreams aiding emotional problem-solving.")
            ],
            "introspective": [
                ("Tonight's symbolic dreams could illuminate hidden aspects of your inner world.",
                 "Inspired by psychologist Dr. Carl Jung's work on dream symbolism and the unconscious."),
                ("Your vivid dreams tonight may reveal insights about your subconscious concerns.",
                 "Based on psychologist Dr. Michael Schredl's research linking dream recall to personality traits."),
                ("Dream imagery tonight might reflect your deepest values and intuitions.",
                 "Interpretation influenced by psychologist Dr. Clara Hill's dream meaning exploration methods.")
            ],
            "lucid": [
                ("Tonight, set a gentle intention: 'I'll become aware that I'm dreaming.'",
                 "Inspired by psychophysiologist Dr. Stephen LaBerge's techniques on inducing lucid dreams."),
                ("Your dreams tonight could offer an opportunity to consciously explore your dreamscape.",
                 "Based on neuroscientist Dr. Benjamin Baird's research on awareness during dreams."),
                ("Before sleep, calmly remind yourself to notice dream signs. Tonight awareness is within reach.",
                 "Guided by psychologist Dr. Ursula Voss's work on lucid dreaming and brain states.")
            ],
            "creative": [
                ("Tonight your dreams may creatively blend ideas, inspiring fresh insights upon waking.",
                 "Interpretation based on psychologist Dr. Ernest Hartmann's thin-boundary dreaming theory."),
                ("Expect imaginative dreams tonight. Tomorrow, capture ideas sparked in your sleep.",
                 "Inspired by neuroscientist Dr. Robert Stickgold's findings on creativity and dreaming."),
                ("Your dreams tonight might reveal unexpected connections. Stay open to morning inspiration.",
                 "Influenced by psychologist Dr. Deirdre Barrett's research on creative problem-solving through dreams.")
            ],
            "resolving": [
                ("Tonight your mind naturally rehearses solutions. Tomorrow, reflect on new approaches to current challenges.",
                 "Inspired by psychologist Dr. G. William Domhoff's work on dreams as problem-solving rehearsals."),
                ("Dreams tonight might simulate future scenarios, quietly preparing you for upcoming events.",
                 "Based on psychologist Dr. Antti Revonsuo's simulation theory of dreaming."),
                ("Your dreams tonight could clarify unresolved issues, helping you awaken with clearer direction.",
                 "Influenced by psychologist Dr. Rosalind Cartwright's findings on dreams and conflict resolution.")
            ]
        }[archetype_id]
    ]
    
    # Select message based on day
    message_pool = messages[0] if messages else []
    if not message_pool:
        return None
        
    selected = message_pool[day_of_year % len(message_pool)]
    
    return DailyMessageRead(
        message=selected[0],
        inspiration=selected[1]
    )

# ─────────────────────────────── profile endpoints ─────────────────────────────── #

@router.get("/me/profile", response_model=ProfileRead, name="get_user_profile")
async def get_user_profile(
    user_id: UUID = Depends(get_current_user_id),
    svc: ProfileService = Depends(get_profile_service),
    user_repo: "UserRepository" = Depends(get_user_repository),
    db: AsyncSession = Depends(get_session),
):
    """Get the current user's profile."""
    # Get user info for name
    user = await user_repo.get_by_id(user_id, db)
    user_name = user.name if user else None
    print(f"DEBUG: User ID: {user_id}, User Name: '{user_name}', User Email: {user.email if user else None}")
    
    profile = await svc.get_user_profile(user_id, db)
    
    if not profile:
        # Return minimal profile if none exists yet
        return ProfileRead(
            name=user_name,
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
    
    # Build complete archetype details
    archetype_details = None
    if display_archetype and display_archetype in ARCHETYPES:
        archetype_data = ARCHETYPES[display_archetype]
        archetype_details = ArchetypeRead(
            id=display_archetype,
            name=archetype_data["name"],
            symbol=archetype_data["symbol"],
            description=archetype_data["description"],
            researcher=archetype_data["researcher"],
            theory=archetype_data["theory"],
            daily_message=generate_daily_message(display_archetype)
        )
    
    return ProfileRead(
        name=user_name,
        archetype=display_archetype,  # Keep for backwards compatibility
        archetype_details=archetype_details,
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

@router.delete("/me", name="delete_user_account")
async def delete_user_account(
    user_id: UUID = Depends(get_current_user_id),
    svc: ProfileService = Depends(get_profile_service),
    user_repo: "UserRepository" = Depends(get_user_repository),
    db: AsyncSession = Depends(get_session),
):
    """Delete the current user's account and all associated data."""
    await svc.delete_user_account(user_id, user_repo, db)
    await db.commit()
    
    return {"message": "Account deleted successfully"}


# ─────────────────────────────── astrology endpoints ─────────────────────────────── #

@router.post("/me/birth-chart", response_model=BirthChartResponse, name="calculate_birth_chart")
async def calculate_birth_chart(
    request: BirthChartRequest,
    user_id: UUID = Depends(get_current_user_id),
):
    """Calculate birth chart - only requires birth date, time, and place name."""
    
    # Initialize services
    birth_chart_service = BirthChartService()
    location_service = get_location_service()
    
    # Validate location
    if not location_service.validate_location(request.birth_place):
        raise HTTPException(
            status_code=400,
            detail="Invalid birth place. Please provide a city and country (e.g., 'New York, NY' or 'London, UK')"
        )
    
    try:
        # Geocode the location
        location_data = await location_service.geocode_location(request.birth_place)
        
        if not location_data:
            raise HTTPException(
                status_code=400,
                detail=f"Could not find location '{request.birth_place}'. Please try a more specific location like 'City, State' or 'City, Country'"
            )
        
        # Get default house system based on location
        house_system = location_service.get_default_house_system(location_data.get('country', ''))
        
        logger.info(f"Geocoded {request.birth_place} -> {location_data['latitude']}, {location_data['longitude']}, {location_data['timezone']}")
        
        # Validate the final birth data
        validation_errors = birth_chart_service.validate_birth_data(
            birth_date=str(request.birth_date),
            birth_time=request.birth_time,
            timezone=location_data['timezone'],
            latitude=location_data['latitude'],
            longitude=location_data['longitude']
        )
        
        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail=f"Validation errors: {validation_errors}"
            )
        
        # Calculate birth chart
        chart_data = birth_chart_service.calculate_birth_chart(
            birth_date=str(request.birth_date),
            birth_time=request.birth_time,
            timezone=location_data['timezone'],
            latitude=location_data['latitude'],
            longitude=location_data['longitude'],
            birth_place=location_data['formatted_address'],
            house_system=house_system
        )
        
        logger.info(f"Birth chart calculated for user {user_id} - {location_data['formatted_address']}")
        return BirthChartResponse(**chart_data)
        
    except HTTPException:
        raise
    except ImportError as e:
        logger.error(f"Birth chart calculation failed - missing dependency: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Birth chart service unavailable. Astrology library not installed."
        )
    except ValueError as e:
        logger.error(f"Birth chart calculation failed for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error calculating birth chart: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Birth chart calculation failed"
        )


@router.post("/me/birth-chart/advanced", response_model=BirthChartResponse, name="calculate_birth_chart_advanced")
async def calculate_birth_chart_advanced(
    request: BirthChartRequestAdvanced,
    user_id: UUID = Depends(get_current_user_id),
):
    """Calculate birth chart with manual coordinates (for advanced users/debugging)."""
    
    birth_chart_service = BirthChartService()
    
    # Validate input data
    validation_errors = birth_chart_service.validate_birth_data(
        birth_date=str(request.birth_date),
        birth_time=request.birth_time,
        timezone=request.timezone,
        latitude=request.latitude,
        longitude=request.longitude
    )
    
    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail=f"Validation errors: {validation_errors}"
        )
    
    try:
        # Calculate birth chart with provided coordinates
        chart_data = birth_chart_service.calculate_birth_chart(
            birth_date=str(request.birth_date),
            birth_time=request.birth_time,
            timezone=request.timezone,
            latitude=request.latitude,
            longitude=request.longitude,
            birth_place=request.birth_place,
            house_system=request.house_system
        )
        
        logger.info(f"Advanced birth chart calculated for user {user_id} - {request.birth_place}")
        return BirthChartResponse(**chart_data)
        
    except ImportError as e:
        logger.error(f"Birth chart calculation failed - missing dependency: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Birth chart service unavailable. Astrology library not installed."
        )
    except ValueError as e:
        logger.error(f"Birth chart calculation failed for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error calculating birth chart: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Birth chart calculation failed"
        )


@router.get("/birth-chart/house-systems", name="get_house_systems")
async def get_supported_house_systems():
    """Get list of supported house systems."""
    birth_chart_service = BirthChartService()
    return {
        "house_systems": birth_chart_service.get_supported_house_systems()
    }