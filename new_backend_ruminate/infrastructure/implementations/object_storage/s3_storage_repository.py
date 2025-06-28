from functools import lru_cache
import boto3
from botocore.client import Config
import asyncio
from uuid import UUID
from typing import Tuple

from new_backend_ruminate.domain.object_storage.repo import ObjectStorageRepository
from new_backend_ruminate.config import settings  # your existing Settings

@lru_cache
def _boto3_client():
    return boto3.client(
        's3',
        aws_access_key_id=settings().aws_access_key,
        aws_secret_access_key=settings().aws_secret_key,
        region_name=settings().aws_region,
        config=Config(signature_version='s3v4')
    )


class S3StorageRepository(ObjectStorageRepository):
    def __init__(self) -> None:
        self._client = _boto3_client()
        self._bucket = settings().s3_bucket

    async def generate_presigned_get(self, did: UUID, filename: str) -> Tuple[str, str]:
        key = f"dreams/{did}/{filename}"
        loop = asyncio.get_running_loop()
        return key, await loop.run_in_executor(
            None,
            lambda: self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=600,
            ),
        )

    async def generate_presigned_put(self, did: UUID, filename: str) -> Tuple[str, str]:
        key = f"dreams/{did}/{filename}"
        loop = asyncio.get_running_loop()
        return key, await loop.run_in_executor(
            None,
            lambda: self._client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=600,
            ),
        )

    async def delete_object(self, key: str) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.delete_object(Bucket=self._bucket, Key=key),
        )
    
    async def generate_presigned_get_by_key(self, key: str) -> str:
        """Generate presigned URL for a specific S3 key"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=3600,  # 1 hour expiry
            ),
        )