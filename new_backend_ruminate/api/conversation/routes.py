# new_backend/api/conversation/routes.py
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from new_backend_ruminate.api.conversation.schemas import MessageIdsResponse, SendMessageRequest, MessageOut
from new_backend_ruminate.api.conversation.schemas import ConversationOut, ConversationInitResponse
from new_backend_ruminate.dependencies import (
    get_conversation_service, 
    get_event_hub,
    get_session,
)
from new_backend_ruminate.services.conversation.service import ConversationService
from new_backend_ruminate.infrastructure.sse.hub import EventStreamHub

router = APIRouter(prefix="/conversations")

@router.post(
    "",
    status_code=201,
    response_model=ConversationInitResponse,
)
async def create_conversation(
    # optional future body with {"type": "...", "meta": {...}}
    body: dict = None,
    svc: ConversationService = Depends(get_conversation_service),
):
    conv_id, root_id = await svc.create_conversation(**(body or {}))
    return {"conversation_id": conv_id, "system_msg_id": root_id}

@router.post("/{cid}/messages", response_model=MessageIdsResponse)
async def post_message(
    cid: str,
    req: SendMessageRequest,
    bg: BackgroundTasks,
    svc: ConversationService = Depends(get_conversation_service),
):
    user_id, ai_id = await svc.send_message(
        background=bg,
        conv_id=cid,
        user_content=req.content,
        parent_id=req.parent_id,
    )
    return {"user_msg_id": user_id, "ai_msg_id": ai_id}


@router.put("/{cid}/messages/{mid}/edit_streaming", response_model=MessageIdsResponse)
async def edit_message(
    cid: str,
    mid: str,
    req: SendMessageRequest,
    bg: BackgroundTasks,
    svc: ConversationService = Depends(get_conversation_service),
):
    edited_id, ai_id = await svc.edit_message_streaming(
        background=bg,
        conv_id=cid,
        msg_id=mid,
        new_content=req.content,
    )
    return {"user_msg_id": edited_id, "ai_msg_id": ai_id}


@router.get("/streams/{msg_id}")
async def stream(msg_id: str, hub: EventStreamHub = Depends(get_event_hub)):
    async def event_source():
        async for chunk in hub.register_consumer(msg_id):
            yield f"data: {chunk}\n\n"
    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.get("/{cid}/thread", response_model=List[MessageOut])
async def get_thread(
    cid: str,
    session: AsyncSession = Depends(get_session),
    svc: ConversationService = Depends(get_conversation_service),
):
    return await svc.get_latest_thread(cid, session)


@router.get("/{cid}/tree", response_model=List[MessageOut])
async def get_tree(
    cid: str,
    session: AsyncSession = Depends(get_session),
    svc: ConversationService = Depends(get_conversation_service),
):
    return await svc.get_full_tree(cid, session)


@router.get("/{cid}/messages/{mid}/versions", response_model=List[MessageOut])
async def versions(
    cid: str,
    mid: str,
    session: AsyncSession = Depends(get_session),
    svc: ConversationService = Depends(get_conversation_service),
):
    return await svc.get_versions(mid, session)


@router.get("/{cid}", response_model=ConversationOut)
async def get_conversation(
    cid: str,
    session: AsyncSession = Depends(get_session),
    svc: ConversationService = Depends(get_conversation_service),
):
    return await svc.get_conversation(cid, session)
