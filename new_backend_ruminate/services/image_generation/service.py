"""
Image Generation Service using OpenAI DALL-E 3
"""
import logging
from typing import Optional, Tuple
from openai import AsyncOpenAI
import aiohttp
import asyncio
from uuid import UUID
import uuid
from new_backend_ruminate.config import settings
from new_backend_ruminate.infrastructure.implementations.object_storage.s3_storage_repository import S3StorageRepository

logger = logging.getLogger(__name__)


class ImageGenerationService:
    """Service for generating dream images using DALL-E 3"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings().openai_api_key)
        self.storage = S3StorageRepository()
    
    async def generate_image(
        self, 
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate an image using DALL-E 3
        
        Args:
            prompt: The text prompt for image generation
            size: Image size (1024x1024, 1792x1024, or 1024x1792)
            quality: "standard" or "hd"
            style: "vivid" or "natural"
            
        Returns:
            Tuple of (image URL, error type) where error type can be:
            - None: Success
            - "content_policy_violation": Content was flagged
            - "error": Other error
        """
        try:
            logger.info(f"Generating image with prompt: {prompt[:100]}...")
            
            response = await self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                style=style,
                n=1
            )
            
            image_url = response.data[0].url
            logger.info(f"Image generated successfully: {image_url}")
            return image_url, None
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Error generating image: {error_str}")
            
            # Check for content policy violation
            if "content_policy_violation" in error_str:
                logger.warning(f"Content policy violation for prompt: {prompt[:100]}...")
                return None, "content_policy_violation"
            
            return None, "error"
    
    async def generate_and_store_image(
        self,
        user_id: UUID,
        dream_id: UUID,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Generate an image and store it in S3
        
        Returns:
            Tuple of (S3 URL, actual prompt used, error type) where error type can be:
            - None: Success
            - "content_policy_violation": Content was flagged
            - "error": Other error
        """
        try:
            # Generate image
            dalle_url, error_type = await self.generate_image(prompt, size, quality, style)
            if not dalle_url:
                return None, None, error_type
            
            # Download image from DALL-E
            async with aiohttp.ClientSession() as session:
                async with session.get(dalle_url) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to download image from DALL-E: {resp.status}")
                        return None, None
                    
                    image_data = await resp.read()
            
            # Generate S3 key
            image_id = str(uuid.uuid4())
            s3_key = f"dreams/{user_id}/{dream_id}/image_{image_id}.png"
            
            # Upload to S3
            logger.info(f"Uploading image to S3: {s3_key}")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self.storage._client.put_object(
                    Bucket=self.storage._bucket,
                    Key=s3_key,
                    Body=image_data,
                    ContentType='image/png'
                )
            )
            
            # Generate presigned URL for reading
            s3_url = await self.storage.generate_presigned_get_by_key(s3_key)
            logger.info(f"Image uploaded successfully to S3: {s3_key}")
            
            return s3_url, prompt, None
            
        except Exception as e:
            logger.error(f"Error in generate_and_store_image: {str(e)}")
            return None, None, "error"
    
    async def test_generation(self) -> Optional[str]:
        """Test image generation with a hardcoded prompt"""
        test_prompt = "A surreal dreamscape with floating books transforming into butterflies against a cosmic purple sky"
        url, _ = await self.generate_image(test_prompt)
        return url