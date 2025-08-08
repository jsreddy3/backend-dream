# new_backend_ruminate/api/checkin/routes.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List
import logging

from new_backend_ruminate.services.checkin.service import CheckInService
from new_backend_ruminate.dependencies import (
    get_session,
    get_checkin_service,
    get_current_user_id,
)
from .schemas import (
    CheckInCreate, 
    CheckInRead, 
    CheckInList,
    InsightGenerationRequest,
    InsightResponse,
    RecentInsightsResponse
)

# for background session scope
from new_backend_ruminate.infrastructure.db.bootstrap import session_scope

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/checkins",
    tags=["checkins"]
)


@router.post("/", response_model=CheckInRead, status_code=status.HTTP_201_CREATED)
async def create_checkin(
    checkin_data: CheckInCreate,
    session: AsyncSession = Depends(get_session),
    checkin_service: CheckInService = Depends(get_checkin_service),
    user_id: UUID = Depends(get_current_user_id)
):
    """Create a new daily check-in."""
    try:
        logger.info(f"[checkins] create: user={user_id}")
        checkin = await checkin_service.create_checkin(
            user_id=user_id,
            checkin_text=checkin_data.checkin_text,
            mood_scores=checkin_data.mood_scores,
            session=session
        )
        return CheckInRead.model_validate(checkin)
    except Exception as e:
        logger.error(f"Error creating check-in for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create check-in"
        )


@router.get("/", response_model=CheckInList)
async def list_checkins(
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    checkin_service: CheckInService = Depends(get_checkin_service),
    user_id: UUID = Depends(get_current_user_id)
):
    """List recent check-ins for the authenticated user."""
    try:
        checkins = await checkin_service.list_recent_checkins(
            user_id=user_id,
            session=session,
            limit=min(limit, 50)  # Cap at 50
        )
        return CheckInList(
            checkins=[CheckInRead.model_validate(checkin) for checkin in checkins],
            total_count=len(checkins)
        )
    except Exception as e:
        logger.error(f"Error listing check-ins for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve check-ins"
        )


@router.get("/{checkin_id}", response_model=CheckInRead)
async def get_checkin(
    checkin_id: UUID,
    session: AsyncSession = Depends(get_session),
    checkin_service: CheckInService = Depends(get_checkin_service),
    user_id: UUID = Depends(get_current_user_id)
):
    """Get a specific check-in."""
    try:
        checkin = await checkin_service.get_checkin(
            user_id=user_id,
            checkin_id=checkin_id,
            session=session
        )
        if not checkin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Check-in not found"
            )
        return CheckInRead.model_validate(checkin)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving check-in {checkin_id} for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve check-in"
        )


@router.post("/{checkin_id}/generate-insight")
async def generate_insight(
    checkin_id: UUID,
    request: InsightGenerationRequest = InsightGenerationRequest(),
    tasks: BackgroundTasks = None,
    session: AsyncSession = Depends(get_session),
    checkin_service: CheckInService = Depends(get_checkin_service),
    user_id: UUID = Depends(get_current_user_id)
):
    """Trigger (or return) insight for a check-in. Runs generation in the background and returns immediately."""
    try:
        logger.info(f"[checkins] generate-insight: user={user_id} checkin={checkin_id} force={request.force_regenerate}")
        # Ensure the check-in exists
        checkin = await checkin_service.get_checkin(user_id, checkin_id, session)
        if not checkin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check-in not found")

        # If we already have a completed insight and not forcing, just return it
        if not request.force_regenerate and checkin.insight_status == "completed" and checkin.insight_text:
            metadata = checkin.context_metadata or {}
            return InsightResponse(
                checkin_id=checkin.id,
                insight_text=checkin.insight_text,
                insight_status=checkin.insight_status,
                key_themes=metadata.get("key_themes"),
                confidence=metadata.get("confidence"),
                generated_at=checkin.insight_generated_at
            )

        # Otherwise, kick off background generation with a fresh session
        async def _task():
            try:
                logger.info(f"[checkins] bg start: user={user_id} checkin={checkin_id}")
                async with session_scope() as s:
                    await checkin_service.generate_insight(user_id=user_id, checkin_id=checkin_id, session=s)
                logger.info(f"[checkins] bg done: user={user_id} checkin={checkin_id}")
            except Exception as e:
                logger.exception(f"[checkins] bg failed: user={user_id} checkin={checkin_id} err={e}")

        if tasks is not None:
            tasks.add_task(_task)
        else:
            # Fallback if BackgroundTasks not available (e.g. in tests)
            import asyncio
            asyncio.create_task(_task())

        return {
            "status": "processing",
            "message": "Insight generation queued",
            "checkin_id": str(checkin_id)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating insight for check-in {checkin_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate insight"
        )


@router.get("/insights/recent", response_model=RecentInsightsResponse)
async def get_recent_insights(
    limit: int = 5,
    session: AsyncSession = Depends(get_session),
    checkin_service: CheckInService = Depends(get_checkin_service),
    user_id: UUID = Depends(get_current_user_id)
):
    """Get recent insights overview."""
    try:
        checkins = await checkin_service.list_recent_checkins(
            user_id=user_id,
            session=session,
            limit=limit
        )
        # Filter to completed insights only
        completed_insights = [
            checkin for checkin in checkins 
            if checkin.insight_status == "completed" and checkin.insight_text
        ]
        insights = []
        for checkin in completed_insights:
            metadata = checkin.context_metadata or {}
            insights.append(InsightResponse(
                checkin_id=checkin.id,
                insight_text=checkin.insight_text,
                insight_status=checkin.insight_status,
                key_themes=metadata.get("key_themes"),
                confidence=metadata.get("confidence"),
                generated_at=checkin.insight_generated_at
            ))
        # Calculate simple streak (consecutive days with check-ins)
        streak = len(checkins) if checkins else 0
        return RecentInsightsResponse(
            insights=insights,
            user_streak=streak,
            total_insights=len(completed_insights)
        )
    except Exception as e:
        logger.error(f"Error retrieving recent insights for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve insights"
        )