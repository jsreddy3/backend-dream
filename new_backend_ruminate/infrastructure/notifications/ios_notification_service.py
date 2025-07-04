from aioapns import APNs
from new_backend_ruminate.domain.ports.ios_push_service import NotificationService
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from new_backend_ruminate.domain.ios.repo import DeviceRepository
from aioapns import NotificationRequest, PushType
from aioapns.common import NotificationResult
import asyncio

class IOSNotificationService(NotificationService):
    def __init__(self, apns: APNs, repo: DeviceRepository):
        self.apns = apns
        self.repo = repo

    async def send_notification(self, *, user_id: UUID, dream_id: UUID, session: AsyncSession):
        # 1. fetch all tokens for this user
        devices = await self.repo.list_by_user(user_id, session)
        if not devices:
            return

        # 2. build requests
        reqs = [
            NotificationRequest(
                device_token=d.token,
                message={
                    "aps": {
                        "alert": {
                            "title": "Your dream video is ready ✨",
                            "body":  "Tap to watch it now",
                        },
                        "sound": "default",
                        "badge": 1,
                    },
                    "dream_id": str(dream_id),
                },
                push_type=PushType.ALERT,
            )
            for d in devices
        ]

        # 3. fan-out (aioapns is async; do it concurrently)
        results = await asyncio.gather(
            *(self.apns.send_notification(r) for r in reqs),
            return_exceptions=True,
        )

        # 4. prune invalid tokens
        for d, res in zip(devices, results):
            if not isinstance(res, NotificationResult):
                continue                          # ← network/other exception, keep token
            if res.status in (400, 403, 410):
                # 400 BadDeviceToken, 403 TopicDisallowed, 410 Unregistered
                await self.repo.delete_by_token(d.token, session)