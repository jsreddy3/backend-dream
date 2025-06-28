import asyncio
import tempfile
import os
from pathlib import Path
from typing import Tuple, Dict, List
from openai import AsyncOpenAI
import logging
import time
import re

from .config import CONFIG, OPENAI_API_KEY
from .models import ScenesData

logger = logging.getLogger("uvicorn")

async def generate_audio_with_transcripts(scenes_data: ScenesData, output_dir: Path) -> Tuple[Dict[int, Dict], float]:
    config = CONFIG["pipeline"]["audio_generation"]
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    voiceovers_dir = output_dir / "voiceovers"
    voiceovers_dir.mkdir(exist_ok=True)
    
    transcriptions_dir = output_dir / "transcriptions"
    transcriptions_dir.mkdir(exist_ok=True)
    
    audio_data = {}
    total_cost = 0.0
    
    logger.info(f"  [Audio] Generating {len(scenes_data.scenes)} voiceovers with {config['voice']} voice")
    start_time = time.time()
    
    # Generate voiceovers in parallel
    tasks = []
    for scene in scenes_data.scenes:
        task = generate_single_voiceover_with_transcription(
            client, scene.scene_id, scene.voiceover_script, 
            config["voice"], config["instructions"], config["speed"]
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    generation_time = time.time() - start_time
    logger.info(f"  [Audio] Generation completed in {generation_time:.1f}s")
    
    # Save results
    for result in results:
        scene_id = result["scene_id"]
        
        # Save audio file
        audio_path = voiceovers_dir / f"scene_{scene_id:02d}_voiceover.mp3"
        with open(audio_path, 'wb') as f:
            f.write(result["audio_data"])
        
        # Save transcription data
        transcription_path = transcriptions_dir / f"scene_{scene_id:02d}_transcription.txt"
        with open(transcription_path, 'w') as f:
            f.write(result["transcript"])
        
        audio_data[scene_id] = {
            "audio_path": str(audio_path),  # Convert Path to string for JSON serialization
            "transcript": result["transcript"],
            "words": result["words"],
            "duration": result["duration"]
        }
        
        total_cost += result["cost_usd"]
        logger.info(f"  [Audio] Scene {scene_id}: {result['duration']:.1f}s duration, {len(result['words'])} words")
    
    total_time = time.time() - start_time
    logger.info(f"  [Audio] ✓ All audio generated in {total_time:.1f}s")
    
    return audio_data, total_cost

def align_whisper_with_script(
    original_script: str,
    whisper_words: List[Dict]
) -> List[Dict]:
    """
    Align Whisper word timestamps with the original script to preserve punctuation and formatting.
    
    Args:
        original_script: The original script text with proper punctuation
        whisper_words: List of word dictionaries from Whisper with 'word', 'start', 'end' keys
    
    Returns:
        List of aligned word dictionaries with proper punctuation and timing
    """
    if not whisper_words or not original_script:
        return whisper_words
    
    # Split on whitespace but keep everything together
    tokens = re.findall(r"\S+", original_script)
    
    # Process tokens to separate words from punctuation while tracking positions
    script_words = []
    for token in tokens:
        # Check if token starts with quotes or punctuation
        leading_punct = ""
        match = re.match(r'^(["\'\u2018\u2019\u201c\u201d`]+)', token)
        if match:
            leading_punct = match.group(1)
            token = token[len(leading_punct):]
        
        # Extract the core word (letters/numbers/apostrophes)
        word_match = re.match(r"^([\w']+)", token)
        if word_match:
            word = word_match.group(1)
            trailing = token[len(word):]  # Everything after the word
            
            # Store as complete word with punctuation
            full_word = leading_punct + word + trailing
            script_words.append({
                'original': full_word,
                'word_only': word.lower(),  # For matching
                'has_word': True
            })
        elif leading_punct:
            # Just punctuation, no word
            script_words.append({
                'original': leading_punct,
                'word_only': '',
                'has_word': False
            })
    
    # Simple matching: go through Whisper words and match with script words
    aligned = []
    script_idx = 0
    
    for whisper_word in whisper_words:
        whisper_clean = re.sub(r'[^\w]', '', whisper_word['word'].lower())
        
        # Find next matching word in script
        while script_idx < len(script_words):
            if script_words[script_idx]['has_word']:
                script_clean = re.sub(r'[^\w]', '', script_words[script_idx]['word_only'])
                if script_clean == whisper_clean:
                    # Found a match! Use script formatting with Whisper timing
                    aligned.append({
                        'word': script_words[script_idx]['original'],
                        'start': whisper_word['start'],
                        'end': whisper_word['end']
                    })
                    script_idx += 1
                    break
                else:
                    # No match, maybe script has extra punctuation or word
                    # Skip if it's just punctuation
                    if not script_words[script_idx]['has_word']:
                        script_idx += 1
                    else:
                        # Word mismatch - this is unexpected for TTS
                        # Use Whisper word but log warning
                        logger.warning(f"Word mismatch: Whisper '{whisper_clean}' vs Script '{script_clean}'")
                        aligned.append(whisper_word)
                        break
            else:
                # Just punctuation in script, skip it
                script_idx += 1
        else:
            # Ran out of script words, just use Whisper word
            aligned.append(whisper_word)
    
    # Handle any remaining script punctuation at the end
    while script_idx < len(script_words):
        if not script_words[script_idx]['has_word'] and aligned:
            # Attach trailing punctuation to last word
            aligned[-1]['word'] += script_words[script_idx]['original']
        script_idx += 1
    
    return aligned

async def generate_single_voiceover_with_transcription(
    client: AsyncOpenAI, 
    scene_id: int, 
    script: str,
    voice: str,
    instructions: str,
    speed: float
) -> Dict:
    # Generate voiceover
    tts_params = {
        "model": "gpt-4o-mini-tts",
        "voice": voice,
        "input": script,
        "speed": speed
    }
    
    if instructions:
        tts_params["instructions"] = instructions
    
    response = await client.audio.speech.create(**tts_params)
    audio_data = response.read()
    
    # Calculate TTS cost: $0.015 per minute
    # Estimate duration based on text length (rough approximation)
    words = len(script.split())
    estimated_duration = words / 3.0  # Assume ~180 WPM
    tts_cost = (estimated_duration / 60.0) * 0.015
    
    # Transcribe for word-level timestamps
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
        tmp_file.write(audio_data)
        tmp_file_path = tmp_file.name
    
    try:
        with open(tmp_file_path, "rb") as audio_file:
            transcription = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word"]
            )
    finally:
        os.unlink(tmp_file_path)
    
    # Extract word timestamps
    words = []
    if hasattr(transcription, 'words') and transcription.words:
        for word in transcription.words:
            words.append({
                "word": word.word,
                "start": word.start,
                "end": word.end
            })
    
    # Align Whisper words with original script to preserve punctuation
    words = align_whisper_with_script(script, words)
    
    # Get actual duration from transcription
    duration = getattr(transcription, 'duration', estimated_duration)
    
    # Calculate transcription cost: $0.006 per minute
    transcription_cost = (duration / 60.0) * 0.006
    
    total_cost = tts_cost + transcription_cost
    
    return {
        "scene_id": scene_id,
        "audio_data": audio_data,
        "transcript": transcription.text,
        "words": words,
        "duration": duration,
        "cost_usd": total_cost
    }