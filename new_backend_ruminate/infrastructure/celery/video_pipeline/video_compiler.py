import asyncio
import subprocess
import tempfile
import os
from pathlib import Path
from typing import List, Dict
import json
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

async def compile_video(
    scenes_data: ScenesData,
    image_paths: List[Path],
    audio_data: Dict[int, Dict],
    output_dir: Path
) -> Path:
    config = CONFIG["pipeline"]["video_compilation"]
    start_time = time.time()
    
    logger.info(f"  [Video] Creating subtitles ({config['subtitle_style']} style, mode: {config.get('subtitle_display_mode', 'kinetic')})")
    
    # Create subtitles
    subtitle_path = create_kinetic_subtitles(
        scenes_data, 
        audio_data, 
        output_dir, 
        config["subtitle_style"],
        config.get("subtitle_display_mode", "kinetic"),
        config.get("subtitle_timing_offset", 0.0),
        config.get("subtitle_font_size", None)
    )
    subtitle_time = time.time() - start_time
    logger.info(f"  [Video] Subtitles created in {subtitle_time:.1f}s")
    
    # Build FFmpeg command
    logger.info(f"  [Video] Building video with FFmpeg ({config['resolution']}, transitions: {config['transitions']})")
    filter_complex_parts = []
    inputs = []
    audio_inputs = []
    
    # Add all images as inputs with their durations
    for i, (scene, img_path) in enumerate(zip(scenes_data.scenes, image_paths)):
        duration = audio_data[scene.scene_id]["duration"]
        inputs.extend(['-loop', '1', '-t', str(duration), '-i', str(img_path)])
    
    # Add all audio files
    for scene in scenes_data.scenes:
        audio_path = audio_data[scene.scene_id]["audio_path"]
        inputs.extend(['-i', audio_path])  # Already a string now
    
    # Scale and pad images to target resolution
    target_res = config["resolution"].split('x')
    width, height = int(target_res[0]), int(target_res[1])
    
    for i in range(len(scenes_data.scenes)):
        scale_filter = f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        
        if config["transitions"] and i > 0:
            fade_duration = config["fade_duration_seconds"]
            scene_duration = audio_data[scenes_data.scenes[i].scene_id]["duration"]
            scale_filter += f",fade=t=in:st=0:d={fade_duration}"
            if i < len(scenes_data.scenes) - 1:
                scale_filter += f",fade=t=out:st={scene_duration - fade_duration}:d={fade_duration}"
        
        scale_filter += f"[v{i}]"
        filter_complex_parts.append(scale_filter)
    
    # Concatenate video streams
    concat_videos = ''.join(f"[v{i}]" for i in range(len(scenes_data.scenes)))
    filter_complex_parts.append(f"{concat_videos}concat=n={len(scenes_data.scenes)}:v=1:a=0[outv]")
    
    # Concatenate audio streams
    audio_offset = len(scenes_data.scenes)
    concat_audios = ''.join(f"[{audio_offset + i}:a]" for i in range(len(scenes_data.scenes)))
    filter_complex_parts.append(f"{concat_audios}concat=n={len(scenes_data.scenes)}:v=0:a=1[outa]")
    
    # Apply subtitles
    filter_complex_parts.append(f"[outv]ass={str(subtitle_path)}[final]")
    
    filter_complex = ';'.join(filter_complex_parts)
    
    # Output path
    output_path = output_dir / "final_video.mp4"
    
    # Build FFmpeg command
    cmd = [
        'ffmpeg', '-y',
        *inputs,
        '-filter_complex', filter_complex,
        '-map', '[final]',
        '-map', '[outa]',
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        str(output_path)
    ]
    
    # Run FFmpeg
    ffmpeg_start = time.time()
    logger.info(f"  [Video] Running FFmpeg...")
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        logger.error(f"  [Video] FFmpeg failed: {stderr.decode()}")
        raise Exception(f"FFmpeg failed: {stderr.decode()}")
    
    ffmpeg_time = time.time() - ffmpeg_start
    total_time = time.time() - start_time
    
    # Check output file size
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"  [Video] ✓ Video compiled in {ffmpeg_time:.1f}s (Total: {total_time:.1f}s)")
    logger.info(f"  [Video] Output: {output_path.name} ({file_size_mb:.2f} MB)")
    
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