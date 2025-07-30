"""GPT-4o-based transcription adapter implementing the TranscriptionService port."""
from __future__ import annotations

import io
import httpx
from openai import AsyncOpenAI
import logging
import time
from typing import Optional

from new_backend_ruminate.config import settings
from new_backend_ruminate.domain.ports.transcription import TranscriptionService

logger = logging.getLogger(__name__)


class GPT4oTranscriptionService(TranscriptionService):
    """Fetch the audio from object-storage and ask GPT-4o-Transcribe for text."""

    _MODEL = "gpt-4o-transcribe"        # full-accuracy model (use *-mini* for cheaper)
    _ENDPOINT_TIMEOUT_S = 60            # network + OpenAI request timeout
    
    # Pricing constants (USD per million tokens)
    _AUDIO_IN_RATE = 6.00
    _TEXT_OUT_RATE = 10.00

    def __init__(self) -> None:
        # One client instance is cheap and fully async-safe
        self._client = AsyncOpenAI(api_key=settings().openai_api_key)

    # ───────────────────────── public API (port impl) ───────────────────────── #
    
    def _calculate_cost(self, usage) -> float:
        """Calculate the transcription cost based on token usage."""
        audio_in = usage.input_token_details.audio_tokens
        text_out = usage.output_tokens
        cost = (audio_in / 1_000_000) * self._AUDIO_IN_RATE + \
               (text_out / 1_000_000) * self._TEXT_OUT_RATE
        return cost

    async def transcribe(self, presigned_url: str) -> str:
        """Download the audio at `presigned_url`, then return its transcript."""
        try:
            start_time = time.time()
            logger.info("GPT-4o Transcription Starting")
            logger.debug(f"URL: {presigned_url[:100]}...")
            
            # 1) Pull the file from your S3/GCS signed URL ─────────────────────────
            download_start = time.time()
            async with httpx.AsyncClient(timeout=self._ENDPOINT_TIMEOUT_S) as http:
                audio_resp = await http.get(presigned_url)
                audio_resp.raise_for_status()
                download_time = time.time() - download_start
                file_size_mb = len(audio_resp.content) / (1024 * 1024)
                logger.debug(f"Downloaded audio: {file_size_mb:.2f} MB in {download_time:.2f}s")

            # 2) Pass the bytes straight to OpenAI ────────────────────────────────
            #    (OpenAI requires a file-like object; BytesIO keeps everything in-memory)
            audio_file = io.BytesIO(audio_resp.content)

            logger.debug(f"Calling OpenAI API with model: {self._MODEL}")
            api_start = time.time()
            response = await self._client.audio.transcriptions.create(
                model=self._MODEL,
                file=("audio.m4a", audio_file),
                # Optional extras:
                # language="en",         # force English decoding if you know the language
                # response_format="text" # "text" is default; "srt"/"vtt" also supported
            )
            api_time = time.time() - api_start

            # Calculate cost and extract metrics
            if hasattr(response, 'usage') and response.usage:
                try:
                    cost = self._calculate_cost(response.usage)
                except AttributeError as e:
                    logger.warning(f"Error calculating cost: {e}")
                    cost = 0.0
                
                # Initialize default values
                audio_tokens = 0
                text_tokens = 0
                
                # Extract tokens based on format
                if isinstance(response.usage, dict):
                    if 'input_token_details' in response.usage and isinstance(response.usage['input_token_details'], dict):
                        audio_tokens = response.usage['input_token_details'].get('audio_tokens', 0)
                    else:
                        audio_tokens = response.usage.get('prompt_tokens', 0)
                    text_tokens = response.usage.get('completion_tokens', response.usage.get('output_tokens', 0))
                
                # Estimate audio duration (approximately 100 tokens per second)
                estimated_duration_seconds = audio_tokens / 100 if audio_tokens > 0 else 0
                
                logger.info(f"Transcription metrics - Duration: ~{estimated_duration_seconds:.1f}s, API time: {api_time:.2f}s, Cost: ${cost:.6f}, Tokens: {audio_tokens} audio, {text_tokens} text")
            
            # Log transcript info (not the full text for privacy)
            logger.debug(f"Transcript generated, length: {len(response.text)} chars")
            
            total_time = time.time() - start_time
            logger.info(f"GPT-4o Transcription Complete - Total time: {total_time:.2f} seconds")
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error in GPT-4o transcription: {str(e)}")
            raise