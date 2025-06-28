"""Deepgram-based transcription adapter implementing the domain TranscriptionService port."""
from __future__ import annotations

import httpx

from new_backend_ruminate.config import settings
from new_backend_ruminate.domain.ports.transcription import TranscriptionService
from new_backend_ruminate.domain.object_storage.repo import ObjectStorageRepository


class DeepgramTranscriptionService(TranscriptionService):
    """Use Deepgram API plus our object-storage repo to fetch transcripts."""

    _ENDPOINT = "https://api.deepgram.com/v1/listen"

    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Token {settings().deepgram_api_key}",
            "Content-Type": "application/json",
        }

    # ───────────────────────── public API (port impl) ────────────────────────── #

    async def transcribe(self, presigned_url: str) -> str:
        print("Calling transcription")
        payload = {
            "url": presigned_url,
            "model": "nova-2",
            "language": "en-US",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(self._ENDPOINT, headers=self._headers, json=payload)

        if resp.status_code != 200:
            raise RuntimeError(f"Deepgram error {resp.status_code}: {resp.text}")

        data = resp.json()
        transcription = data["results"]["channels"][0]["alternatives"][0]["transcript"]
        print("Transcription: ", transcription)
        return transcription
