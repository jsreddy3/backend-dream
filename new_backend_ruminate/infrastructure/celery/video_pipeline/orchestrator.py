import asyncio
from pathlib import Path
from typing import Tuple, Dict, Any
import json
import time
import logging

from .config import CONFIG
from .models import ScenesData
from .dream_parser import parse_dream
from .image_generator import generate_images
from .audio_generator import generate_audio_with_transcripts
from .video_compiler import compile_video

logger = logging.getLogger("uvicorn")

class VideoPipeline:
    def __init__(self):
        self.config = CONFIG["pipeline"]
        self.storage_config = CONFIG["storage"]
    
    async def generate_video(self, dream_text: str, job_id: str) -> Tuple[Path, float, Dict[str, Any]]:
        pipeline_start = time.time()
        logger.info(f"[Job {job_id[:8]}] Starting video generation pipeline")
        
        output_dir = Path(self.storage_config["local_path"]) / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        total_cost = 0.0
        metadata = {}
        
        # Stage 1: Parse dream into scenes
        logger.info(f"[Job {job_id[:8]}] Stage 1: Parsing dream text ({len(dream_text)} chars)")
        stage1_start = time.time()
        scenes_data, parse_cost = await parse_dream(dream_text)
        stage1_time = time.time() - stage1_start
        logger.info(f"[Job {job_id[:8]}] ✓ Stage 1 complete in {stage1_time:.1f}s - Generated {len(scenes_data.scenes)} scenes (${parse_cost:.4f})")
        
        total_cost += parse_cost
        metadata["scenes"] = scenes_data.dict()
        
        # Save scenes data
        scenes_file = output_dir / "scenes.json"
        with open(scenes_file, 'w') as f:
            json.dump(scenes_data.dict(), f, indent=2)
        
        # Log scene details
        for scene in scenes_data.scenes:
            logger.info(f"[Job {job_id[:8]}]   Scene {scene.scene_id}: {scene.summary[:50]}...")
        
        # Stage 2 & 3 can run in parallel
        logger.info(f"[Job {job_id[:8]}] Stage 2&3: Generating images and audio in parallel")
        parallel_start = time.time()
        
        image_task = generate_images(scenes_data, output_dir)
        audio_task = generate_audio_with_transcripts(scenes_data, output_dir)
        
        (image_paths, image_cost), (audio_data, audio_cost) = await asyncio.gather(
            image_task, audio_task
        )
        
        parallel_time = time.time() - parallel_start
        logger.info(f"[Job {job_id[:8]}] ✓ Stage 2&3 complete in {parallel_time:.1f}s")
        logger.info(f"[Job {job_id[:8]}]   Images: ${image_cost:.4f}, Audio: ${audio_cost:.4f}")
        
        total_cost += image_cost + audio_cost
        metadata["image_paths"] = [str(p) for p in image_paths]
        metadata["audio_data"] = audio_data
        
        # Stage 4: Compile video
        logger.info(f"[Job {job_id[:8]}] Stage 4: Compiling video with kinetic subtitles")
        stage4_start = time.time()
        video_path = await compile_video(
            scenes_data=scenes_data,
            image_paths=image_paths,
            audio_data=audio_data,
            output_dir=output_dir
        )
        stage4_time = time.time() - stage4_start
        logger.info(f"[Job {job_id[:8]}] ✓ Stage 4 complete in {stage4_time:.1f}s")
        
        metadata["total_cost"] = round(total_cost, 4)
        metadata["video_path"] = str(video_path)
        
        # Add config parameters used for generation
        metadata["config"] = {
            "scene_parsing": self.config["scene_parsing"],
            "image_generation": self.config["image_generation"],
            "audio_generation": self.config["audio_generation"],
            "video_compilation": self.config["video_compilation"]
        }
        
        # Save metadata
        metadata_file = output_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        total_time = time.time() - pipeline_start
        logger.info(f"[Job {job_id[:8]}] ✅ Pipeline complete in {total_time:.1f}s - Total cost: ${total_cost:.4f}")
        
        return video_path, total_cost, metadata