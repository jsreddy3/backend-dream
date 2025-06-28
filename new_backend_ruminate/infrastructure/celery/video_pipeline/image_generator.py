import asyncio
import base64
from pathlib import Path
from typing import List, Tuple, Dict
import aiohttp
from openai import AsyncOpenAI
import logging
import time

from .config import CONFIG, OPENAI_API_KEY
from .models import ScenesData

logger = logging.getLogger("uvicorn")

IMAGE_PRICING = {
    "dall-e-2": {
        "256x256": 0.016,
        "512x512": 0.018,
        "1024x1024": 0.020
    },
    "dall-e-3": {
        "standard": 0.040,
        "hd": 0.080
    },
    "gpt-image-1": {
        "low": 0.01,
        "medium": 0.04,
        "high": 0.17
    }
}

async def generate_images(scenes_data: ScenesData, output_dir: Path) -> Tuple[List[Path], float]:
    config = CONFIG["pipeline"]["image_generation"]
    model = config["model"]
    
    if model == "dall-e-2":
        return await generate_dalle2_images(scenes_data, output_dir)
    elif model == "dall-e-3":
        return await generate_dalle3_images(scenes_data, output_dir)
    elif model == "gpt-image-1":
        return await generate_gpt_image_1_images(scenes_data, output_dir)
    else:
        raise ValueError(f"Unknown image model: {model}")

async def generate_dalle2_images(scenes_data: ScenesData, output_dir: Path) -> Tuple[List[Path], float]:
    config = CONFIG["pipeline"]["image_generation"]
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)
    
    image_paths = []
    total_cost = 0.0
    
    logger.info(f"  [Images] Generating {len(scenes_data.scenes)} images with DALL-E 2 ({config['size']})")
    start_time = time.time()
    
    # Generate images in parallel for DALL-E 2
    tasks = []
    for scene in scenes_data.scenes:
        task = generate_single_dalle2_image(client, scene.scene_id, scene.visual_prompt, config["size"])
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    api_time = time.time() - start_time
    logger.info(f"  [Images] API calls completed in {api_time:.1f}s")
    
    # Download images and save
    download_start = time.time()
    async with aiohttp.ClientSession() as session:
        for i, result in enumerate(results):
            scene_id = result["scene_id"]
            image_url = result["image_url"]
            cost = result["cost_usd"]
            
            # Download image
            async with session.get(image_url) as resp:
                image_data = await resp.read()
            
            # Save image
            image_path = images_dir / f"scene_{scene_id:02d}.png"
            with open(image_path, 'wb') as f:
                f.write(image_data)
            
            image_paths.append(image_path)
            total_cost += cost
            logger.info(f"  [Images] Scene {scene_id} image saved ({len(image_data)/1024:.1f} KB)")
    
    download_time = time.time() - download_start
    total_time = time.time() - start_time
    logger.info(f"  [Images] ✓ All images generated in {total_time:.1f}s (API: {api_time:.1f}s, Download: {download_time:.1f}s)")
    
    return image_paths, total_cost

async def generate_single_dalle2_image(client: AsyncOpenAI, scene_id: int, prompt: str, size: str) -> Dict:
    try:
        response = await client.images.generate(
            model="dall-e-2",
            prompt=prompt,
            size=size,
            n=1
        )
        
        return {
            "scene_id": scene_id,
            "image_url": response.data[0].url,
            "cost_usd": IMAGE_PRICING["dall-e-2"][size]
        }
    except Exception as e:
        logger.error(f"  [Images] Error generating image for scene {scene_id}: {str(e)}")
        logger.error(f"  [Images] Prompt was: {prompt[:100]}...")
        raise

async def generate_dalle3_images(scenes_data: ScenesData, output_dir: Path) -> Tuple[List[Path], float]:
    config = CONFIG["pipeline"]["image_generation"]
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)
    
    image_paths = []
    total_cost = 0.0
    
    # Generate images in parallel for DALL-E 3
    tasks = []
    for scene in scenes_data.scenes:
        task = generate_single_dalle3_image(
            client, scene.scene_id, scene.visual_prompt, 
            config.get("size", "1024x1024"), config.get("quality", "standard")
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    # Download images and save
    async with aiohttp.ClientSession() as session:
        for result in results:
            scene_id = result["scene_id"]
            image_url = result["image_url"]
            cost = result["cost_usd"]
            
            # Download image
            async with session.get(image_url) as resp:
                image_data = await resp.read()
            
            # Save image
            image_path = images_dir / f"scene_{scene_id:02d}.png"
            with open(image_path, 'wb') as f:
                f.write(image_data)
            
            image_paths.append(image_path)
            total_cost += cost
    
    return image_paths, total_cost

async def generate_single_dalle3_image(client: AsyncOpenAI, scene_id: int, prompt: str, size: str, quality: str) -> Dict:
    response = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=size,
        quality=quality,
        n=1
    )
    
    return {
        "scene_id": scene_id,
        "image_url": response.data[0].url,
        "cost_usd": IMAGE_PRICING["dall-e-3"][quality]
    }

async def generate_gpt_image_1_images(scenes_data: ScenesData, output_dir: Path) -> Tuple[List[Path], float]:
    config = CONFIG["pipeline"]["image_generation"]
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)
    
    image_paths = []
    total_cost = 0.0
    prev_response_id = None
    
    # Must be sequential for context continuity
    for scene in scenes_data.scenes:
        response = await client.responses.create(
            model="gpt-4o-mini",
            input=scene.visual_prompt,
            previous_response_id=prev_response_id,
            tools=[{
                "type": "image_generation",
                "size": "1024x1024",
                "quality": config.get("quality", "medium")
            }]
        )
        
        # Extract image
        img_b64 = None
        for output in response.output:
            if output.type == "image_generation_call":
                img_b64 = output.result
                break
        
        if not img_b64:
            raise ValueError(f"No image generated for scene {scene.scene_id}")
        
        # Save image
        image_path = images_dir / f"scene_{scene.scene_id:02d}.png"
        with open(image_path, 'wb') as f:
            f.write(base64.b64decode(img_b64))
        
        image_paths.append(image_path)
        
        # Calculate cost
        usage = response.usage
        token_cost = (usage.input_tokens * 0.15 + usage.output_tokens * 0.60) / 1_000_000
        image_cost = IMAGE_PRICING["gpt-image-1"][config.get("quality", "medium")]
        total_cost += token_cost + image_cost
        
        prev_response_id = response.id
    
    return image_paths, total_cost