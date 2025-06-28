# new_backend_ruminate/domain/conversation/repo.py
from abc import ABC, abstractmethod
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from new_backend_ruminate.domain.conversation.entities.message import Message
from new_backend_ruminate.domain.conversation.entities.conversation import Conversation
from uuid import UUID


class ConversationRepository(ABC):
    # creation / reads
    @abstractmethod
    async def create(self, conv: Conversation, session: AsyncSession) -> Conversation: ...
    @abstractmethod
    async def get(self, cid: UUID, session: AsyncSession) -> Optional[Conversation]: ...
    @abstractmethod
    async def latest_thread(self, cid: UUID, session: AsyncSession) -> List[Message]: ...
    @abstractmethod
    async def full_tree(self, cid: UUID, session: AsyncSession) -> List[Message]: ...
    @abstractmethod
    async def message_versions(self, mid: UUID, session: AsyncSession) -> List[Message]: ...

    # mutations
    @abstractmethod
    async def add_message(self, msg: Message, session: AsyncSession) -> None: ...
    @abstractmethod
    async def edit_message(
        self, msg_id: UUID, new_content: str, session: AsyncSession
    ) -> tuple[Message, str]: ...
    @abstractmethod
    async def set_active_child(self, parent_id: UUID, child_id: UUID, session: AsyncSession) -> None: ...
    @abstractmethod
    async def update_message_content(self, mid: UUID, new: str, session: AsyncSession) -> None: ...
    @abstractmethod
    async def update_active_thread(self, cid: UUID, thread: list[UUID], session: AsyncSession) -> None: ...
