"""GPT-4o-based transcription adapter implementing the TranscriptionService port."""
from __future__ import annotations

import io
import httpx
from openai import AsyncOpenAI
import logging

from new_backend_ruminate.config import settings
from new_backend_ruminate.domain.ports.transcription import TranscriptionService

logger = logging.getLogger(__name__)


class GPT4oTranscriptionService(TranscriptionService):
    """Fetch the audio from object-storage and ask GPT-4o-Transcribe for text."""

    _MODEL = "gpt-4o-transcribe"        # full-accuracy model (use *-mini* for cheaper)
    _ENDPOINT_TIMEOUT_S = 60            # network + OpenAI request timeout

    def __init__(self) -> None:
        # One client instance is cheap and fully async-safe
        self._client = AsyncOpenAI(api_key=settings().openai_api_key)

    # ───────────────────────── public API (port impl) ───────────────────────── #

    async def transcribe(self, presigned_url: str) -> str:
        """Download the audio at `presigned_url`, then return its transcript."""
        try:
            logger.info(f"Starting GPT-4o transcription for URL: {presigned_url[:100]}...")
            
            # 1) Pull the file from your S3/GCS signed URL ─────────────────────────
            async with httpx.AsyncClient(timeout=self._ENDPOINT_TIMEOUT_S) as http:
                audio_resp = await http.get(presigned_url)
                audio_resp.raise_for_status()
                logger.info(f"Downloaded audio file, size: {len(audio_resp.content)} bytes")

            # 2) Pass the bytes straight to OpenAI ────────────────────────────────
            #    (OpenAI requires a file-like object; BytesIO keeps everything in-memory)
            audio_file = io.BytesIO(audio_resp.content)

            logger.info(f"Calling OpenAI API with model: {self._MODEL}")
            response = await self._client.audio.transcriptions.create(
                model=self._MODEL,
                file=("audio.m4a", audio_file),
                # Optional extras:
                # language="en",         # force English decoding if you know the language
                # response_format="text" # "text" is default; "srt"/"vtt" also supported
            )

            # The SDK already flattens the response → just use `.text`
            logger.info(f"Transcription successful, length: {len(response.text)} characters")
            return response.text
            
        except Exception as e:
            logger.error(f"Error in GPT-4o transcription: {str(e)}")
            raise