from new_backend_ruminate.config import settings
from new_backend_ruminate.domain.ports.transcription import TranscriptionService
import httpx

class WhisperTranscriptionService(TranscriptionService):
    _ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"

    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {settings().openai_api_key}",
        }

    async def transcribe(self, presigned_url: str) -> str:
        # 1️⃣  fetch the audio (streaming so we don't load it all into RAM)
        async with httpx.AsyncClient(timeout=None) as client:
            src = await client.get(presigned_url, timeout=None)
            src.raise_for_status()          # presigned URL still valid?

            # 2️⃣  read the audio content into memory (httpx multipart expects a bytes-like object with a read() method)
            audio_bytes: bytes = await src.aread()

            files = {
                # name, bytes-like-obj, MIME-type
                "file": ("input", audio_bytes, src.headers.get("Content-Type", "audio/wav")),
                "model": (None, "whisper-1"),
                # optional extras:
                # "language": (None, "en"),
                # "temperature": (None, "0.0"),
            }

            resp = await client.post(
                self._ENDPOINT,
                headers=self._headers,
                files=files,
                timeout=300,                 # Whisper can take a while
            )

        if resp.status_code != 200:
            raise RuntimeError(f"Whisper error {resp.status_code}: {resp.text}")

        transcription = resp.json()["text"]
        return transcription
