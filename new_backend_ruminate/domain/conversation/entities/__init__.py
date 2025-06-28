# new_backend_ruminate/domain/__init__.py
"""
Import every ORM model so that Base.metadata is fully populated
before Alembic autogenerate interrogates it.
"""

from new_backend_ruminate.domain.conversation.entities.conversation import Conversation  # noqa: F401
from new_backend_ruminate.domain.conversation.entities.message import Message            # noqa: F401
# add future models here, one per line
