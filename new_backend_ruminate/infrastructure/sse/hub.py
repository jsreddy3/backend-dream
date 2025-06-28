# new_backend_ruminate/infrastructure/sse/hub.py

import asyncio
import logging
from collections import defaultdict
from typing import AsyncIterator, Dict, List
from uuid import UUID

logger = logging.getLogger(__name__)


class EventStreamHub:
    """
    In-process publish/subscribe hub.  Multiple consumers per stream are
    supported by maintaining a list[Queue] for each stream_id.
    """

    def __init__(self) -> None:
        self._queues: Dict[UUID, List[asyncio.Queue[str]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def register_consumer(self, stream_id: UUID) -> AsyncIterator[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._queues[stream_id].append(q)

        try:
            while True:
                chunk = await q.get()
                if chunk is None:                           # termination sentinel
                    return
                yield chunk
        finally:
            async with self._lock:
                lst = self._queues.get(stream_id)
                if lst and q in lst:
                    lst.remove(q)
                    if not lst:
                        self._queues.pop(stream_id, None)

    async def publish(self, stream_id: UUID, chunk: str) -> None:
        async with self._lock:
            queues = self._queues.get(stream_id, [])
            for q in queues:
                await q.put(chunk)

    async def terminate(self, stream_id: UUID) -> None:
        async with self._lock:
            queues = self._queues.pop(stream_id, [])
            for q in queues:
                await q.put(None)
