from abc import ABC, abstractmethod
from uuid import UUID

class TranscriptionService(ABC):
    @abstractmethod
    async def transcribe(self, presigned_url: str) -> str: ...