from abc import ABC, abstractmethod
from typing import Tuple
from uuid import UUID

class ObjectStorageRepository (ABC):
    """Interface for storage repositories"""
    @abstractmethod
    async def generate_presigned_get(self, did: UUID, filename: str) -> Tuple[str, str]: ...

    @abstractmethod
    async def generate_presigned_put(self, did: UUID, filename: str) -> Tuple[str, str]: ...

    @abstractmethod
    async def delete_object(self, key: str) -> None: ...
    
    @abstractmethod
    async def generate_presigned_get_by_key(self, key: str) -> str: 
        """Generate presigned URL for a specific S3 key"""
        ...