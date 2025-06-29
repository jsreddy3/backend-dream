import asyncio
import subprocess
import tempfile
import os
from pathlib import Path
from typing import List, Dict
import json
import psutil, asyncio, statistics, shlex
import logging
import time

from .config import CONFIG
from .models import ScenesData

logger = logging.getLogger("uvicorn")

SUBTITLE_STYLES = {
    "modern": {
        "fontname": "Arial Black",
        "fontsize": 48,
        "bold": True,
        "primary_color": "&H00FFFFFF",
        "secondary_color": "&H00FFB300",
        "outline_color": "&H00000000",
        "back_color": "&H80000000",
        "outline": 2,
        "shadow": 1,
        "alignment": 2,
        "margin_v": 60
    },
    "tiktok": {
        "fontname": "Arial Black",
        "fontsize": 56,
        "bold": True,
        "primary_color": "&H00FFFFFF",
        "secondary_color": "&H00000000",
        "outline_color": "&H00000000",
        "back_color": "&H80000000",
        "outline": 3,
        "shadow": 2,
        "alignment": 2,
        "margin_v": 80
    },
    "minimal": {
        "fontname": "Helvetica",
        "fontsize": 42,
        "bold": False,
        "primary_color": "&H00FFFFFF",
        "secondary_color": "&H00CCCCCC",
        "outline_color": "&H00333333",
        "back_color": "&H00000000",
        "outline": 1,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 50
    },
    "dramatic": {
        "fontname": "Impact",
        "fontsize": 64,
        "bold": True,
        "primary_color": "&H00FFFF00",
        "secondary_color": "&H0000FFFF",
        "outline_color": "&H00000000",
        "back_color": "&HCC000000",
        "outline": 4,
        "shadow": 3,
        "alignment": 2,
        "margin_v": 100
    }
}

async def _run_with_mem(cmd: list[str]) -> list[int]:
    """Launch cmd with asyncio and sample its RSS every 250 ms.
       Returns the list of samples in bytes."""
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    samples = []
    p = psutil.Process(proc.pid)
    async def sampler():
        while proc.returncode is None:
            try:
                samples.append(p.memory_info().rss)
            except psutil.Error:
                break
            await asyncio.sleep(0.25)
    task = asyncio.create_task(sampler())
    _, stderr = await proc.communicate()
    await task
    if proc.returncode:                           # propagate failure
        raise RuntimeError(stderr.decode()[:300])
    return samples

async def _encode_scene(
    scene,
    img_path: Path,
    audio_info: Dict,
    tmp_dir: Path,
    cfg: Dict,
) -> Path:
    """
    Encode *one* scene into an MP4 with its own burned-in kinetic subtitles.
    Returns the path to the temporary clip.
    """
    # 1️⃣  Build a one-scene ASS file
    sub_path = create_kinetic_subtitles(
        ScenesData(dream_summary="", scenes=[scene], total_duration_sec=int(audio_info["duration"])),
        {scene.scene_id: audio_info},
        tmp_dir,
        cfg["subtitle_style"],
        cfg.get("subtitle_display_mode", "kinetic"),
        cfg.get("subtitle_timing_offset", 0.0),
        cfg.get("subtitle_font_size"),
    )

    dur   = audio_info["duration"]
    w, h  = map(int, cfg["resolution"].split("x"))
    fade  = cfg["fade_duration_seconds"]
    clip  = tmp_dir / f"scene_{scene.scene_id}.mp4"

    ff_filter = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
        f"fade=t=in:st=0:d={fade},"
        f"fade=t=out:st={dur - fade}:d={fade},"
        f"ass={shlex.quote(sub_path.as_posix())}[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(dur), "-i", str(img_path),
        "-i", audio_info["audio_path"],
        "-filter_complex", ff_filter,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264",
        "-preset", cfg.get("preset", "ultrafast"),
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-threads", "1",
        str(clip),
    ]

    # Run FFmpeg while sampling its memory usage
    def _cg_mem_mb() -> float:
        with open("/sys/fs/cgroup/memory.current") as f:
            return int(f.read()) / (1024**2)
    logger.info("cgroup before FFmpeg %.0f MB", _cg_mem_mb())
    mem_samples = await _run_with_mem(cmd)
    logger.info("cgroup after FFmpeg %.0f MB", _cg_mem_mb())
    if mem_samples:
        peak_mb = max(mem_samples) / (1024 ** 2)
        mean_mb = statistics.mean(mem_samples) / (1024 ** 2)
        logger.info(
            f"      [Scene {scene.scene_id}] FFmpeg peak RSS {peak_mb:.1f} MB (avg {mean_mb:.1f} MB)"
        )
    return clip


async def compile_video(
    scenes_data: ScenesData,
    image_paths: List[Path],
    audio_data: Dict[int, Dict],
    output_dir: Path,
) -> Path:
    """
    Memory-friendly pipeline:

      1.  Encode each scene individually  (≈ 80 MB RSS per job)
      2.  Stream-copy concatenate the resulting clips (≈ 20 MB RSS)

    Peak memory stays below ~100 MB even for 3×1080p scenes.
    """
    cfg = CONFIG["pipeline"]["video_compilation"]
    start = time.time()

    # ── 1️⃣  Scene-by-scene pass ─────────────────────────────────────────
    logger.info("  [Video] Encoding %d scene(s) sequentially …", len(scenes_data.scenes))
    tmp_dir = output_dir / "_chunks"
    tmp_dir.mkdir(exist_ok=True)

    clip_paths: List[Path] = []
    for scene, img in zip(scenes_data.scenes, image_paths):
        clip = await _encode_scene(scene, img, audio_data[scene.scene_id], tmp_dir, cfg)
        clip_paths.append(clip)

    # ── 2️⃣  Concat pass (stream-copy, zero re-encode) ───────────────────
    concat_list = tmp_dir / "list.txt"
    with concat_list.open("w") as f:
        for p in clip_paths:
            f.write(f"file '{p.resolve()}'\n")

    output_path = output_dir / "final_video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy",
        str(output_path),
    ]
    logger.info("  [Video] Concatenating %d clip(s) …", len(clip_paths))
    # Run concat pass with memory profiling
    mem_samples = await _run_with_mem(cmd)
    if mem_samples:
        peak_mb = max(mem_samples) / (1024 ** 2)
        mean_mb = statistics.mean(mem_samples) / (1024 ** 2)
        logger.info(
            f"  [Video] Concat FFmpeg peak RSS {peak_mb:.1f} MB (avg {mean_mb:.1f} MB)"
        )

    total = time.time() - start
    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("  [Video] ✓ Done in %.1fs → %s (%.2f MB)", total, output_path.name, size_mb)

    return output_path

def create_kinetic_subtitles(
    scenes_data: ScenesData,
    audio_data: Dict[int, Dict],
    output_dir: Path,
    style_name: str,
    display_mode: str = "kinetic",
    timing_offset: float = 0.0,
    font_size: int = None
) -> Path:
    style = SUBTITLE_STYLES.get(style_name, SUBTITLE_STYLES["modern"]).copy()
    
    # Override font size if specified
    if font_size is not None:
        logger.info(f"  [Video] Overriding {style_name} font size from {style['fontsize']} to {font_size}")
        style["fontsize"] = font_size
    
    # Build ASS header
    ass_content = "[Script Info]\n"
    ass_content += "Title: Kinetic Subtitles\n"
    ass_content += "ScriptType: v4.00+\n"
    ass_content += "WrapStyle: 0\n"
    ass_content += "ScaledBorderAndShadow: yes\n"
    ass_content += "YCbCr Matrix: TV.601\n"
    ass_content += "PlayResX: 1920\n"
    ass_content += "PlayResY: 1080\n\n"
    
    # Add styles
    ass_content += "[V4+ Styles]\n"
    ass_content += "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    
    bold = "-1" if style.get("bold", True) else "0"
    ass_content += f"Style: Default,{style['fontname']},{style['fontsize']},{style['primary_color']},{style['secondary_color']},{style['outline_color']},{style['back_color']},{bold},0,0,0,100,100,0,0,1,{style['outline']},{style['shadow']},{style['alignment']},10,10,{style['margin_v']},1\n\n"
    
    # Add events
    ass_content += "[Events]\n"
    ass_content += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    
    current_time = 0.0
    
    for scene in scenes_data.scenes:
        words = audio_data[scene.scene_id]["words"]
        scene_start = current_time
        
        # Chunk words into caption events
        events = chunk_words_into_captions(words)
        
        for event in events:
            if not event:
                continue
                
            # Adjust timestamps relative to scene start and apply timing offset
            start_time = scene_start + event[0]['start'] + timing_offset
            end_time = scene_start + event[-1]['end'] + timing_offset
            
            # Ensure timestamps don't go negative
            start_time = max(0, start_time)
            end_time = max(0, end_time)
            
            # Build text based on display mode
            if display_mode == "kinetic":
                # Build karaoke effect text for kinetic mode
                text_parts = []
                for i, word in enumerate(event):
                    word_duration = word['end'] - word['start']
                    k_duration = int(word_duration * 100)
                    
                    if i == 0:
                        text_parts.append(f"{{\\k{k_duration}}}{word['word']}")
                    else:
                        text_parts.append(f" {{\\k{k_duration}}}{word['word']}")
                
                text = "".join(text_parts)
            else:
                # Static mode - all words appear at once
                text = " ".join([word['word'] for word in event])
            
            # Format timestamps
            start_str = format_ass_time(start_time)
            end_str = format_ass_time(end_time)
            
            ass_content += f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n"
        
        current_time += audio_data[scene.scene_id]["duration"]
    
    # Save subtitle file
    subtitle_path = output_dir / "subtitles.ass"
    with open(subtitle_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)
    
    return subtitle_path

def chunk_words_into_captions(
    words: List[Dict],
    max_chars: int = 20,
    max_words: int = 3,
    max_duration: float = 1.8,
    min_gap: float = 0.15
) -> List[List[Dict]]:
    if not words:
        return []
    
    events = []
    bucket = []
    
    for word in words:
        if bucket:
            potential_text = " ".join([w['word'] for w in bucket + [word]])
            potential_duration = word['end'] - bucket[0]['start']
            gap_from_last = word['start'] - bucket[-1]['end']
            
            if (len(bucket) >= max_words or
                len(potential_text) > max_chars or
                potential_duration > max_duration or
                gap_from_last > min_gap):
                events.append(bucket)
                bucket = []
        
        bucket.append(word)
    
    if bucket:
        events.append(bucket)
    
    return events

def format_ass_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"